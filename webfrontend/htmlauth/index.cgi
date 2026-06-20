#!/usr/bin/perl
use strict;
use warnings;
use utf8;
use open qw(:std :encoding(UTF-8));

use CGI;
use HTML::Template;
use Config::Simple;
use JSON;
use FindBin qw($Bin);
use Encode qw(encode decode FB_CROAK);
use LoxBerry::System;
use LoxBerry::Web;

my $cgi          = CGI->new;
my $ajax         = $cgi->param('ajax') // '';
my $config_file  = '/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg';
my $service_name = 'vlx2mqtt.service';
my $default_logfile = '/opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log';

my %DEFAULTS = (
    'vlx2mqtt.klf_host'                    => 'VELUX-KLF-DE3B.fritz.box',
    'vlx2mqtt.klf_pw'                      => 'KLF_WiFi_PASSWORT',
    'vlx2mqtt.mqtt_host'                   => '127.0.0.1',
    'vlx2mqtt.mqtt_port'                   => '1883',
    'vlx2mqtt.mqtt_user'                   => 'loxberry',
    'vlx2mqtt.mqtt_pw'                     => 'MQTT_PASSWORT',
    'vlx2mqtt.root_topic'                  => 'vlx2mqtt',
    'vlx2mqtt.initial_delay'               => '2.5',
    'vlx2mqtt.connect_timeout'             => '30.0',
    'vlx2mqtt.moving_timeout'              => '60.0',
    'vlx2mqtt.backoff_max'                 => '30.0',
    'vlx2mqtt.verbose'                     => '0',
    'vlx2mqtt.logfile'                     => $default_logfile,
    'vlx2mqtt.external_recovery_enabled'   => '0',
    'vlx2mqtt.external_recovery_threshold' => '4',
    'vlx2mqtt.external_recovery_cooldown'  => '1800',
    'vlx2mqtt.external_recovery_grace'     => '120',
    'vlx2mqtt.external_recovery_topic'     => 'vlx2mqtt/recovery/powercycle_required',
    'vlx2mqtt.preventive_recovery_hours'   => '0',
    'vlx2mqtt.topic_identifier'            => 'name',
    'vlx2mqtt.rain_poll_interval'          => '300',
    'vlx2mqtt.publish_rain_raw_limit'      => '0',
);

sub template_path {
    no strict 'vars';
    if (defined $lbptemplatedir && $lbptemplatedir && -e "$lbptemplatedir/index.html") {
        return "$lbptemplatedir/index.html";
    }
    return "$Bin/index.html";
}

sub trim {
    my ($v) = @_;
    $v = '' if !defined $v;
    $v =~ s/^\s+//;
    $v =~ s/\s+$//;
    return $v;
}

sub bool_param {
    my ($name) = @_;
    return defined $cgi->param($name) ? '1' : '0';
}

sub json_out {
    my ($obj) = @_;
    print $cgi->header(-type => 'application/json', -charset => 'utf-8');
    print JSON->new->canonical(1)->encode($obj);
    exit;
}

sub load_cfg_hash {
    my ($file) = @_;
    my %cfg = %DEFAULTS;
    my $cs;
    eval { $cs = Config::Simple->new($file); };
    if (!$@ && $cs) {
        for my $key (keys %DEFAULTS) {
            my $val = eval { $cs->param($key) };
            $cfg{$key} = $val if defined $val;
        }
    }
    return \%cfg;
}

sub save_cfg_hash {
    my ($file, $cfg) = @_;
    my $cs = Config::Simple->new(syntax => 'ini');
    for my $key (sort keys %{$cfg}) {
        $cs->param($key, $cfg->{$key});
    }
    $cs->write($file) or die "Cannot write config $file";
    chmod 0600, $file;
}

sub service_status {
    my $active = qx(systemctl is-active $service_name 2>/dev/null);
    chomp $active;
    $active ||= 'unknown';

    my $pid = qx(systemctl show -p MainPID --value $service_name 2>/dev/null);
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
    my $rc = system("sudo systemctl $action $service_name >/dev/null 2>&1");
    my ($active, $pid) = service_status();
    return {
        error   => ($rc == 0 ? 0 : 1),
        action  => $action,
        state   => $active,
        pid     => $pid,
        message => ($rc == 0 ? 'ok' : "$action failed (rc=$rc)"),
    };
}

sub mqtt_read_topic_once {
    my ($cfg, $topic) = @_;
    return (1, 'Invalid topic', undef) unless defined $topic && $topic ne '';

    my @cmd = (
        'mosquitto_sub',
        '-h', $cfg->{'vlx2mqtt.mqtt_host'},
        '-p', $cfg->{'vlx2mqtt.mqtt_port'},
        '-C', '1',
        '-W', '2',
        '-t', $topic
    );

    push @cmd, ('-u', $cfg->{'vlx2mqtt.mqtt_user'})
        if defined $cfg->{'vlx2mqtt.mqtt_user'} && $cfg->{'vlx2mqtt.mqtt_user'} ne '';
    push @cmd, ('-P', $cfg->{'vlx2mqtt.mqtt_pw'})
        if defined $cfg->{'vlx2mqtt.mqtt_pw'} && $cfg->{'vlx2mqtt.mqtt_pw'} ne '';

    my $pid = open my $fh, '-|', @cmd;
    if (!$pid) {
        return (1, 'Failed to execute mosquitto_sub', undef);
    }

    my $payload = <$fh>;
    close $fh;
    chomp $payload if defined $payload;

    return (1, 'No payload received', undef) if !defined $payload || $payload eq '';
    return (0, 'ok', $payload);
}

sub ensure_utf8 {
    my ($s) = @_;
    return '' if !defined $s;
    return $s if utf8::is_utf8($s);

    my $decoded = eval { decode('UTF-8', $s, FB_CROAK) };
    return defined $decoded ? $decoded : $s;
}

sub maybe_unmangle {
    my ($s) = @_;
    return '' if !defined $s;

    $s = ensure_utf8($s);

    # Repariert typische Mojibake-Muster wie Ã„ / Ã¼ / â€“
    return $s unless $s =~ /(?:Ã.|Â.|â..)/;

    my $fixed = eval { decode('UTF-8', encode('latin1', $s), FB_CROAK) };
    return defined $fixed ? $fixed : $s;
}

sub validate_config {
    my ($cfg) = @_;

    for my $required (qw(vlx2mqtt.klf_host vlx2mqtt.mqtt_host vlx2mqtt.root_topic)) {
        return 'CFG.REQUIRED_FIELD'
            if !defined $cfg->{$required} || trim($cfg->{$required}) eq '';
    }

    return 'CFG.INVALID_MQTT_PORT'
        unless $cfg->{'vlx2mqtt.mqtt_port'} =~ /^\d+$/
            && $cfg->{'vlx2mqtt.mqtt_port'} >= 1
            && $cfg->{'vlx2mqtt.mqtt_port'} <= 65535;

    return 'CFG.INVALID_INITIAL_DELAY'
        unless $cfg->{'vlx2mqtt.initial_delay'} =~ /^\d+(?:\.\d+)?$/;

    return 'CFG.INVALID_CONNECT_TIMEOUT'
        unless $cfg->{'vlx2mqtt.connect_timeout'} =~ /^\d+(?:\.\d+)?$/;

    return 'CFG.INVALID_MOVING_TIMEOUT'
        unless $cfg->{'vlx2mqtt.moving_timeout'} =~ /^\d+(?:\.\d+)?$/;

    return 'CFG.INVALID_BACKOFF_MAX'
        unless $cfg->{'vlx2mqtt.backoff_max'} =~ /^\d+(?:\.\d+)?$/;

    return 'CFG.INVALID_RAIN_POLL_INTERVAL'
        unless $cfg->{'vlx2mqtt.rain_poll_interval'} =~ /^\d+$/
            && $cfg->{'vlx2mqtt.rain_poll_interval'} >= 60;

    return 'CFG.INVALID_RECOVERY_THRESHOLD'
        unless $cfg->{'vlx2mqtt.external_recovery_threshold'} =~ /^\d+$/;

    return 'CFG.INVALID_RECOVERY_COOLDOWN'
        unless $cfg->{'vlx2mqtt.external_recovery_cooldown'} =~ /^\d+(?:\.\d+)?$/;

    return 'CFG.INVALID_RECOVERY_GRACE'
        unless $cfg->{'vlx2mqtt.external_recovery_grace'} =~ /^\d+(?:\.\d+)?$/;

    return 'CFG.INVALID_PREVENTIVE_RECOVERY'
        unless $cfg->{'vlx2mqtt.preventive_recovery_hours'} =~ /^\d+(?:\.\d+)?$/;

    return 'CFG.INVALID_TOPIC_IDENTIFIER'
        unless ($cfg->{'vlx2mqtt.topic_identifier'} || '') =~ /^(?:name|node_id)$/;

    return undef;
}

my $template = HTML::Template->new(
    filename           => template_path(),
    global_vars        => 1,
    loop_context_vars  => 1,
    die_on_bad_params  => 0,
    utf8               => 1,
);

# Wichtig: Sprache NICHT direkt von readlanguage() ins Template schreiben lassen,
# sondern zuerst als Hash holen, ggf. reparieren, und erst dann param() setzen.
my %L = eval { LoxBerry::System::readlanguage('language.ini') };
for my $key (keys %L) {
    $L{$key} = maybe_unmangle($L{$key});
}
$template->param(%L);

sub lang {
    my ($key, $fallback) = @_;
    my $val = exists $L{$key} && defined $L{$key} && $L{$key} ne ''
        ? $L{$key}
        : ($fallback // $key);
    return maybe_unmangle($val);
}

my $cfg = load_cfg_hash($config_file);
my $notice = '';
my $notice_class = 'notice-info';
my $notice_visible = 0;
my $doc_link = 'https://github.com/5iggi/vlx2mqtt_old/blob/main/README_full.md';

if ($ajax) {
    if (check_pin_if_supplied()) {
        json_out({ error => 1, message => 'Invalid PIN' });
    }

    if ($ajax eq 'statusvlx') {
        my ($active, $pid) = service_status();
        my $state_topic = trim($cfg->{'vlx2mqtt.root_topic'}) . '/status_live';
        my ($err, $msg, $payload) = mqtt_read_topic_once($cfg, $state_topic);

        json_out({
            error      => 0,
            pid        => $pid,
            state      => $active,
            message    => ($active eq 'active' ? 'OK' : $active),
            klf_status => ($err ? 'unknown' : $payload),
        });
    }
    elsif ($ajax eq 'restartvlx') {
        json_out(run_service_action('restart'));
    }
    elsif ($ajax eq 'stopvlx') {
        json_out(run_service_action('stop'));
    }
    elsif ($ajax eq 'gettopic') {
        my $topic = trim($cgi->param('topic') // '');
        my ($err, $msg, $payload) = mqtt_read_topic_once($cfg, $topic);

        json_out({
            error   => $err,
            topic   => $topic,
            payload => $payload,
            message => $msg,
        });
    }
    else {
        json_out({ error => 1, message => 'Unknown ajax action' });
    }
}

if ($cgi->param('save')) {
    my %newcfg = %{$cfg};

    $newcfg{'vlx2mqtt.klf_host'} = trim($cgi->param('klf_host'));
    $newcfg{'vlx2mqtt.klf_pw'} = trim($cgi->param('klf_pw'));
    $newcfg{'vlx2mqtt.mqtt_host'} = trim($cgi->param('mqtt_host'));
    $newcfg{'vlx2mqtt.mqtt_port'} = trim($cgi->param('mqtt_port'));
    $newcfg{'vlx2mqtt.mqtt_user'} = trim($cgi->param('mqtt_user'));
    $newcfg{'vlx2mqtt.mqtt_pw'} = trim($cgi->param('mqtt_pw'));
    $newcfg{'vlx2mqtt.root_topic'} = trim($cgi->param('root_topic'));
    $newcfg{'vlx2mqtt.initial_delay'} = trim($cgi->param('initial_delay'));
    $newcfg{'vlx2mqtt.connect_timeout'} = trim($cgi->param('connect_timeout'));
    $newcfg{'vlx2mqtt.moving_timeout'} = trim($cgi->param('moving_timeout'));
    $newcfg{'vlx2mqtt.backoff_max'} = trim($cgi->param('backoff_max'));
    $newcfg{'vlx2mqtt.verbose'} = bool_param('debug_verbose');
    $newcfg{'vlx2mqtt.logfile'} = trim($cgi->param('logfile')) || $default_logfile;
    $newcfg{'vlx2mqtt.topic_identifier'} = trim($cgi->param('topic_identifier')) || 'name';
    $newcfg{'vlx2mqtt.rain_poll_interval'} = trim($cgi->param('rain_poll_interval'));
    $newcfg{'vlx2mqtt.publish_rain_raw_limit'} = bool_param('publish_rain_raw_limit');
    $newcfg{'vlx2mqtt.external_recovery_enabled'} = bool_param('external_recovery_enabled');
    $newcfg{'vlx2mqtt.external_recovery_threshold'} = trim($cgi->param('external_recovery_threshold'));
    $newcfg{'vlx2mqtt.external_recovery_cooldown'} = trim($cgi->param('external_recovery_cooldown'));
    $newcfg{'vlx2mqtt.external_recovery_grace'} = trim($cgi->param('external_recovery_grace'));
    $newcfg{'vlx2mqtt.external_recovery_topic'} =
        trim($cgi->param('external_recovery_topic')) || 'vlx2mqtt/recovery/powercycle_required';
    $newcfg{'vlx2mqtt.preventive_recovery_hours'} = trim($cgi->param('preventive_recovery_hours'));

    my $validation_error = validate_config(\%newcfg);
    if ($validation_error) {
        $notice = lang($validation_error, $validation_error);
        $notice_class = 'notice-error';
        $notice_visible = 1;
        $cfg = \%newcfg;
    } else {
        eval { save_cfg_hash($config_file, \%newcfg); };
        if ($@) {
            $notice = lang('CFG.SAVE_FAILED', 'Saving configuration failed') . ': ' . maybe_unmangle($@);
            $notice_class = 'notice-error';
            $notice_visible = 1;
            $cfg = \%newcfg;
        } else {
            $notice = lang('CFG.SAVE_OK', 'Configuration saved. Please restart the service so the changes become effective.');
            $notice_class = 'notice-success';
            $notice_visible = 1;
            $cfg = \%newcfg;
        }
    }
}

my ($active, $pid) = service_status();
my $service_state = ($active eq 'active') ? 'OK' : 'STOPPED';
my $service_color = ($active eq 'active') ? 'green' : 'gray';

$template->param(
    SERVICE_STATE                       => maybe_unmangle($service_state),
    SERVICE_PID                         => maybe_unmangle($pid),
    SERVICE_COLOR                       => $service_color,
    NOTICE                              => maybe_unmangle($notice),
    NOTICE_CLASS                        => $notice_class,
    NOTICE_VISIBLE                      => $notice_visible,
    DOC_LINK                            => $doc_link,
    klf_host                            => maybe_unmangle($cfg->{'vlx2mqtt.klf_host'}),
    klf_pw                              => maybe_unmangle($cfg->{'vlx2mqtt.klf_pw'}),
    mqtt_host                           => maybe_unmangle($cfg->{'vlx2mqtt.mqtt_host'}),
    mqtt_port                           => maybe_unmangle($cfg->{'vlx2mqtt.mqtt_port'}),
    mqtt_user                           => maybe_unmangle($cfg->{'vlx2mqtt.mqtt_user'}),
    mqtt_pw                             => maybe_unmangle($cfg->{'vlx2mqtt.mqtt_pw'}),
    root_topic                          => maybe_unmangle($cfg->{'vlx2mqtt.root_topic'}),
    initial_delay                       => maybe_unmangle($cfg->{'vlx2mqtt.initial_delay'}),
    connect_timeout                     => maybe_unmangle($cfg->{'vlx2mqtt.connect_timeout'}),
    moving_timeout                      => maybe_unmangle($cfg->{'vlx2mqtt.moving_timeout'}),
    backoff_max                         => maybe_unmangle($cfg->{'vlx2mqtt.backoff_max'}),
    logfile                             => maybe_unmangle($cfg->{'vlx2mqtt.logfile'}),
    debug_verbose_checked               => ($cfg->{'vlx2mqtt.verbose'} ? 'checked' : ''),
    external_recovery_enabled_checked   => ($cfg->{'vlx2mqtt.external_recovery_enabled'} ? 'checked' : ''),
    external_recovery_threshold         => maybe_unmangle($cfg->{'vlx2mqtt.external_recovery_threshold'}),
    external_recovery_cooldown          => maybe_unmangle($cfg->{'vlx2mqtt.external_recovery_cooldown'}),
    external_recovery_grace             => maybe_unmangle($cfg->{'vlx2mqtt.external_recovery_grace'}),
    external_recovery_topic             => maybe_unmangle($cfg->{'vlx2mqtt.external_recovery_topic'}),
    preventive_recovery_hours           => maybe_unmangle($cfg->{'vlx2mqtt.preventive_recovery_hours'}),
    topic_identifier_name_selected      => (($cfg->{'vlx2mqtt.topic_identifier'} || 'name') eq 'name' ? 'selected' : ''),
    topic_identifier_node_id_selected   => (($cfg->{'vlx2mqtt.topic_identifier'} || 'name') eq 'node_id' ? 'selected' : ''),
    rain_poll_interval                  => maybe_unmangle($cfg->{'vlx2mqtt.rain_poll_interval'} || '300'),
    publish_rain_raw_limit_checked      => ($cfg->{'vlx2mqtt.publish_rain_raw_limit'} ? 'checked' : ''),
);

my $plugintitle  = 'VLX2MQTT KLF200 Bridge';
my $helplink     = $doc_link;
my $helptemplate = 'help.html';

LoxBerry::Web::lbheader($plugintitle, $helplink, $helptemplate);
print $template->output();
LoxBerry::Web::lbfooter();
``