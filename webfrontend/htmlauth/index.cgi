#!/usr/bin/perl
use strict;
use warnings;
use utf8;

use CGI;
use HTML::Template;
use Config::Simple;
use JSON;
use FindBin qw($Bin);

use LoxBerry::System;
use LoxBerry::Web;
use LoxBerry::Log;
use LoxBerry::JSON;

my $cgi  = CGI->new;
my $ajax = $cgi->param('ajax') // '';

my $config_file  = '/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg';
my $service_name = 'vlx2mqtt.service';
my $default_logfile = '/opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log';

# ------------------------------------------------------------
# Plugin metadata + navbar
# ------------------------------------------------------------
my $plugin = eval { LoxBerry::System::plugindata() } || {};
our %navbar;
#$navbar{10}{Name} = $plugin->{PLUGINDB_TITLE} || 'vlx2mqtt';
$navbar{10}{Name} = 'VLX2MQTT KLF200 Bridge';
$navbar{10}{URL}  = 'index.cgi';

# ------------------------------------------------------------
# Template path
# ------------------------------------------------------------
sub template_path {
    no strict 'vars';
    if (defined $lbptemplatedir && $lbptemplatedir && -e "$lbptemplatedir/index.html") {
        return "$lbptemplatedir/index.html";
    }
    return "$Bin/index.html";
}

# ------------------------------------------------------------
# CFG helpers (section [vlx2mqtt])
# ------------------------------------------------------------
my %DEFAULTS = (
    'vlx2mqtt.klf_host'                  => 'VELUX-KLF-DE3B.fritz.box',
    'vlx2mqtt.klf_pw'                    => 'KLF_WiFi_PASSWORT',
    'vlx2mqtt.mqtt_host'                 => '127.0.0.1',
    'vlx2mqtt.mqtt_port'                 => '1883',
    'vlx2mqtt.mqtt_user'                 => 'loxberry',
    'vlx2mqtt.mqtt_pw'                   => 'MQTT_PASSWORT',
    'vlx2mqtt.root_topic'                => 'vlx2mqtt',
    'vlx2mqtt.initial_delay'             => '2.5',
    'vlx2mqtt.connect_timeout'           => '30.0',
    'vlx2mqtt.moving_timeout'            => '60.0',
    'vlx2mqtt.backoff_max'               => '30.0',
    'vlx2mqtt.verbose'                   => '0',
    'vlx2mqtt.logfile'                   => $default_logfile,
    'vlx2mqtt.external_recovery_enabled' => '1',
    'vlx2mqtt.external_recovery_threshold' => '4',
    'vlx2mqtt.external_recovery_cooldown' => '1800',
    'vlx2mqtt.external_recovery_grace'   => '120',
    'vlx2mqtt.external_recovery_topic'   => 'vlx2mqtt/recovery/powercycle_required',
    'vlx2mqtt.preventive_recovery_hours' => '24',
    'vlx2mqtt.topic_identifier'           => 'name',
    'vlx2mqtt.rain_poll_interval'         => '300',
    'vlx2mqtt.publish_rain_raw_limit'     => '0',
);

sub load_cfg_hash {
    my ($file) = @_;
    my %cfg = %DEFAULTS;
    my $cobj;
    eval { $cobj = Config::Simple->new($file); };
    if (!$@ && $cobj) {
        foreach my $key (keys %DEFAULTS) {
            my $val = eval { $cobj->param($key) };
            $cfg{$key} = $val if defined $val;
        }
    }
    return \%cfg;
}

sub save_cfg_hash {
    my ($file, $cfg) = @_;
    my $cs = Config::Simple->new(syntax => 'ini');
    foreach my $key (sort keys %{$cfg}) {
        $cs->param($key, $cfg->{$key});
    }
    $cs->write($file) or die "Cannot write config $file";
}

# ------------------------------------------------------------
# Template + language
# ------------------------------------------------------------
my $template = HTML::Template->new(
    filename          => template_path(),
    global_vars       => 1,
    loop_context_vars => 1,
    die_on_bad_params => 0,
);
my %L = eval { LoxBerry::Web::readlanguage($template, 'language.ini') };

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
sub json_out {
    my ($obj) = @_;
    print $cgi->header(-type => 'application/json', -charset => 'utf-8');
    print JSON->new->canonical(1)->encode($obj);
    exit;
}

sub service_status {
    my $active = `systemctl is-active $service_name 2>/dev/null`;
    chomp $active;
    $active = 'unknown' if !$active;

    my $pid = `systemctl show -p MainPID --value $service_name 2>/dev/null`;
    chomp $pid;
    $pid = '-' if !$pid || $pid eq '0';

    return ($active, $pid);
}

sub check_pin_if_supplied {
    my $pin = $cgi->param('secpin');
    return 0 if !defined $pin || $pin eq '';
    my $err = eval { LoxBerry::System::check_securepin($pin) };
    return $err ? 1 : 0;
}

sub run_service_action {
    my ($action) = @_;
    my $rc = system('sudo', 'systemctl', $action, $service_name);
    my ($active, $pid) = service_status();
    return {
        error   => ($rc == 0 ? 0 : 1),
        action  => $action,
        state   => $active,
        pid     => $pid,
        message => ($rc == 0 ? 'ok' : "${action} failed (rc=$rc)"),
    };
}

sub mqtt_read_topic_once {
    my ($cfgref, $topic) = @_;
    return (1, 'Invalid topic', undef) unless $topic =~ m{^[-A-Za-z0-9_/]+$};

    my $host = $cfgref->{'vlx2mqtt.mqtt_host'} || '127.0.0.1';
    my $port = $cfgref->{'vlx2mqtt.mqtt_port'} || '1883';
    my $user = $cfgref->{'vlx2mqtt.mqtt_user'} || '';
    my $pass = $cfgref->{'vlx2mqtt.mqtt_pw'} || '';

    my @cmd = ('/usr/bin/mosquitto_sub', '-h', $host, '-p', $port, '-t', $topic, '-C', '1', '-W', '2');
    push @cmd, ('-u', $user) if $user ne '';
    push @cmd, ('-P', $pass) if $pass ne '';

    return (1, 'mosquitto_sub not found', undef) unless -x $cmd[0];

    my $payload = '';
    my $rc = 1;
    if (open my $fh, '-|', @cmd) {
        local $/;
        $payload = <$fh>;
        close $fh;
        $rc = $? >> 8;
    }

    chomp($payload) if defined $payload;
    return ($rc == 0)
        ? (0, 'ok', $payload)
        : (1, "no retained message or mosquitto_sub failed (rc=$rc)", undef);
}

my $cfg = load_cfg_hash($config_file);

# ------------------------------------------------------------
# AJAX handlers
# ------------------------------------------------------------
if ($ajax) {
    if (check_pin_if_supplied()) {
        json_out({ error => 1, message => 'Invalid PIN' });
    }

    if ($ajax eq 'gettopic') {
        my $root_topic = $cfg->{'vlx2mqtt.root_topic'} || 'vlx2mqtt';
        my $topic = $cgi->param('topic') // '';
        unless ($topic =~ m{^\Q$root_topic\E/[A-Za-z0-9_\-/]+$}) {
            json_out({ error => 1, message => 'Invalid topic' });
        }
        my ($err, $msg, $payload) = mqtt_read_topic_once($cfg, $topic);
        json_out({ error => $err, topic => $topic, payload => $payload, message => $msg });
    }

    if ($ajax eq 'statusvlx') {
        my ($active, $pid) = service_status();
        my $root_topic = $cfg->{'vlx2mqtt.root_topic'} || 'vlx2mqtt';
        my ($err, $msg, $klf_status) = mqtt_read_topic_once($cfg, "$root_topic/status");
        my $message = ($active eq 'active')
            ? ($L{MSG_SERVICE_OK} || 'OK')
            : ($L{MSG_SERVICE_STOPPED} || 'STOPPED');
        json_out({
            error      => 0,
            pid        => $pid,
            state      => $active,
            message    => $message,
            klf_status => ($err ? 'unknown' : $klf_status),
        });
    }

    if ($ajax eq 'restartvlx') {
        json_out(run_service_action('restart'));
    }

    if ($ajax eq 'stopvlx') {
        json_out(run_service_action('stop'));
    }

    json_out({ error => 1, message => "Unknown action '$ajax'" });
}

# ------------------------------------------------------------
# Save handler
# ------------------------------------------------------------
my $notice = '';
if ($cgi->param('save')) {
    my %newcfg = %{$cfg};

    my $klf_host                    = $cgi->param('klf_host')                    // $cfg->{'vlx2mqtt.klf_host'};
    my $klf_pw                      = $cgi->param('klf_pw')                      // $cfg->{'vlx2mqtt.klf_pw'};
    my $mqtt_host                   = $cgi->param('mqtt_host')                   // $cfg->{'vlx2mqtt.mqtt_host'};
    my $mqtt_port                   = $cgi->param('mqtt_port')                   // $cfg->{'vlx2mqtt.mqtt_port'};
    my $mqtt_user                   = $cgi->param('mqtt_user')                   // $cfg->{'vlx2mqtt.mqtt_user'};
    my $mqtt_pw                     = $cgi->param('mqtt_pw')                     // $cfg->{'vlx2mqtt.mqtt_pw'};
    my $root_topic                  = $cgi->param('root_topic')                  // $cfg->{'vlx2mqtt.root_topic'};
    my $initial_delay               = $cgi->param('initial_delay')               // $cfg->{'vlx2mqtt.initial_delay'};
    my $connect_timeout             = $cgi->param('connect_timeout')             // $cfg->{'vlx2mqtt.connect_timeout'};
    my $moving_timeout              = $cgi->param('moving_timeout')              // $cfg->{'vlx2mqtt.moving_timeout'};
    my $backoff_max                 = $cgi->param('backoff_max')                 // $cfg->{'vlx2mqtt.backoff_max'};
    my $logfile                     = $cgi->param('logfile')                     // $cfg->{'vlx2mqtt.logfile'};
    my $external_recovery_enabled   = $cgi->param('external_recovery_enabled') ? 1 : 0;
    my $external_recovery_threshold = $cgi->param('external_recovery_threshold') // $cfg->{'vlx2mqtt.external_recovery_threshold'};
    my $external_recovery_cooldown  = $cgi->param('external_recovery_cooldown')  // $cfg->{'vlx2mqtt.external_recovery_cooldown'};
    my $external_recovery_grace     = $cgi->param('external_recovery_grace')     // $cfg->{'vlx2mqtt.external_recovery_grace'};
    my $external_recovery_topic     = $cgi->param('external_recovery_topic')     // $cfg->{'vlx2mqtt.external_recovery_topic'};
    my $preventive_recovery_hours   = $cgi->param('preventive_recovery_hours')   // $cfg->{'vlx2mqtt.preventive_recovery_hours'};
    my $topic_identifier            = $cgi->param('topic_identifier')            // $cfg->{'vlx2mqtt.topic_identifier'};
    my $rain_poll_interval          = $cgi->param('rain_poll_interval')          // $cfg->{'vlx2mqtt.rain_poll_interval'};
    my $publish_rain_raw_limit      = $cgi->param('publish_rain_raw_limit') ? 1 : 0;
    my $verbose                     = $cgi->param('debug_verbose') ? 1 : 0;

    $mqtt_port                   = ($mqtt_port =~ /^\d+$/) ? int($mqtt_port) : $cfg->{'vlx2mqtt.mqtt_port'};
    $initial_delay               = ($initial_delay =~ /^[0-9]+(?:\.[0-9]+)?$/) ? $initial_delay : $cfg->{'vlx2mqtt.initial_delay'};
    $connect_timeout             = ($connect_timeout =~ /^[0-9]+(?:\.[0-9]+)?$/) ? $connect_timeout : $cfg->{'vlx2mqtt.connect_timeout'};
    $moving_timeout              = ($moving_timeout =~ /^[0-9]+(?:\.[0-9]+)?$/) ? $moving_timeout : $cfg->{'vlx2mqtt.moving_timeout'};
    $backoff_max                 = ($backoff_max =~ /^[0-9]+(?:\.[0-9]+)?$/) ? $backoff_max : $cfg->{'vlx2mqtt.backoff_max'};
    $external_recovery_threshold = ($external_recovery_threshold =~ /^\d+$/) ? int($external_recovery_threshold) : $cfg->{'vlx2mqtt.external_recovery_threshold'};
    $external_recovery_cooldown  = ($external_recovery_cooldown =~ /^[0-9]+(?:\.[0-9]+)?$/) ? $external_recovery_cooldown : $cfg->{'vlx2mqtt.external_recovery_cooldown'};
    $external_recovery_grace     = ($external_recovery_grace =~ /^[0-9]+(?:\.[0-9]+)?$/) ? $external_recovery_grace : $cfg->{'vlx2mqtt.external_recovery_grace'};
    $preventive_recovery_hours   = ($preventive_recovery_hours =~ /^[0-9]+(?:\.[0-9]+)?$/) ? $preventive_recovery_hours : $cfg->{'vlx2mqtt.preventive_recovery_hours'};
    $topic_identifier            = ($topic_identifier && $topic_identifier =~ /^(?:name|node_id)$/) ? $topic_identifier : ($cfg->{'vlx2mqtt.topic_identifier'} || 'name');
    $rain_poll_interval          = ($rain_poll_interval =~ /^\d+$/) ? int($rain_poll_interval) : ($cfg->{'vlx2mqtt.rain_poll_interval'} || 300);

    $newcfg{'vlx2mqtt.klf_host'}                   = $klf_host;
    $newcfg{'vlx2mqtt.klf_pw'}                     = $klf_pw;
    $newcfg{'vlx2mqtt.mqtt_host'}                  = $mqtt_host;
    $newcfg{'vlx2mqtt.mqtt_port'}                  = $mqtt_port;
    $newcfg{'vlx2mqtt.mqtt_user'}                  = $mqtt_user;
    $newcfg{'vlx2mqtt.mqtt_pw'}                    = $mqtt_pw;
    $newcfg{'vlx2mqtt.root_topic'}                 = $root_topic;
    $newcfg{'vlx2mqtt.initial_delay'}              = $initial_delay;
    $newcfg{'vlx2mqtt.connect_timeout'}            = $connect_timeout;
    $newcfg{'vlx2mqtt.moving_timeout'}             = $moving_timeout;
    $newcfg{'vlx2mqtt.backoff_max'}                = $backoff_max;
    $newcfg{'vlx2mqtt.logfile'}                    = $logfile;
    $newcfg{'vlx2mqtt.verbose'}                    = $verbose;
    $newcfg{'vlx2mqtt.external_recovery_enabled'}  = $external_recovery_enabled;
    $newcfg{'vlx2mqtt.external_recovery_threshold'}= $external_recovery_threshold;
    $newcfg{'vlx2mqtt.external_recovery_cooldown'} = $external_recovery_cooldown;
    $newcfg{'vlx2mqtt.external_recovery_grace'}    = $external_recovery_grace;
    $newcfg{'vlx2mqtt.external_recovery_topic'}    = $external_recovery_topic;
    $newcfg{'vlx2mqtt.preventive_recovery_hours'}  = $preventive_recovery_hours;
    $newcfg{'vlx2mqtt.topic_identifier'}            = $topic_identifier;
    $newcfg{'vlx2mqtt.rain_poll_interval'}          = $rain_poll_interval;
    $newcfg{'vlx2mqtt.publish_rain_raw_limit'}      = $publish_rain_raw_limit;

    eval {
        save_cfg_hash($config_file, \%newcfg);
        $cfg = \%newcfg;
        $notice = 'Konfiguration gespeichert.';
        system('sudo', 'systemctl', 'restart', $service_name);
    };
    if ($@) {
        $notice = 'Fehler beim Speichern: ' . $@;
    }
}

# ------------------------------------------------------------
# Service state for template
# ------------------------------------------------------------
my ($service_state, $service_pid, $service_color) = ('', '-', 'gray');
my ($active, $pid) = service_status();
if ($active eq 'active') {
    $service_state = $L{MSG_SERVICE_OK} || 'OK';
    $service_color = 'green';
    $service_pid   = $pid || '-';
} else {
    $service_state = $L{MSG_SERVICE_STOPPED} || 'STOPPED';
    $service_color = 'gray';
}

$template->param(
    SERVICE_STATE                     => $service_state,
    SERVICE_PID                       => $service_pid,
    SERVICE_COLOR                     => $service_color,
    NOTICE                            => $notice,
    klf_host                          => $cfg->{'vlx2mqtt.klf_host'},
    klf_pw                            => $cfg->{'vlx2mqtt.klf_pw'},
    mqtt_host                         => $cfg->{'vlx2mqtt.mqtt_host'},
    mqtt_port                         => $cfg->{'vlx2mqtt.mqtt_port'},
    mqtt_user                         => $cfg->{'vlx2mqtt.mqtt_user'},
    mqtt_pw                           => $cfg->{'vlx2mqtt.mqtt_pw'},
    root_topic                        => $cfg->{'vlx2mqtt.root_topic'},
    initial_delay                     => $cfg->{'vlx2mqtt.initial_delay'},
    connect_timeout                   => $cfg->{'vlx2mqtt.connect_timeout'},
    moving_timeout                    => $cfg->{'vlx2mqtt.moving_timeout'},
    backoff_max                       => $cfg->{'vlx2mqtt.backoff_max'},
    logfile                           => $cfg->{'vlx2mqtt.logfile'},
    debug_verbose_checked             => ($cfg->{'vlx2mqtt.verbose'} ? 'checked' : ''),
    external_recovery_enabled_checked => ($cfg->{'vlx2mqtt.external_recovery_enabled'} ? 'checked' : ''),
    external_recovery_threshold       => $cfg->{'vlx2mqtt.external_recovery_threshold'},
    external_recovery_cooldown        => $cfg->{'vlx2mqtt.external_recovery_cooldown'},
    external_recovery_grace           => $cfg->{'vlx2mqtt.external_recovery_grace'},
    external_recovery_topic           => $cfg->{'vlx2mqtt.external_recovery_topic'},
    preventive_recovery_hours         => $cfg->{'vlx2mqtt.preventive_recovery_hours'},
    topic_identifier_name_selected    => (($cfg->{'vlx2mqtt.topic_identifier'} || 'name') eq 'name' ? 'selected' : ''),
    topic_identifier_node_id_selected => (($cfg->{'vlx2mqtt.topic_identifier'} || 'name') eq 'node_id' ? 'selected' : ''),
    rain_poll_interval                => $cfg->{'vlx2mqtt.rain_poll_interval'} || '300',
    publish_rain_raw_limit_checked    => ($cfg->{'vlx2mqtt.publish_rain_raw_limit'} ? 'checked' : ''),
);

my $plugintitle  = ($plugin->{PLUGINDB_TITLE} || 'vlx2mqtt') . ' ' . ($plugin->{PLUGINDB_VERSION} || '');
my $helplink     = 'https://github.com/5iggi/vlx2mqtt';
my $helptemplate = 'help.html';

LoxBerry::Web::lbheader($plugintitle, $helplink, $helptemplate);
print $template->output();
LoxBerry::Web::lbfooter();
