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
my $download     = $cgi->param('download') // '';
my $config_file  = '/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg';
my $service_name = 'vlx2mqtt.service';
my $default_logfile = '/opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log';

my %DEFAULTS = (
    'vlx2mqtt.klf_host'                    => 'VELUX-KLF.fritz.box',
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


sub mqtt_cmd_base {
    my ($cfg) = @_;
    my @cmd = ('mosquitto_sub', '-h', $cfg->{'vlx2mqtt.mqtt_host'}, '-p', $cfg->{'vlx2mqtt.mqtt_port'});
    push @cmd, ('-u', $cfg->{'vlx2mqtt.mqtt_user'}) if defined $cfg->{'vlx2mqtt.mqtt_user'} && $cfg->{'vlx2mqtt.mqtt_user'} ne '';
    push @cmd, ('-P', $cfg->{'vlx2mqtt.mqtt_pw'}) if defined $cfg->{'vlx2mqtt.mqtt_pw'} && $cfg->{'vlx2mqtt.mqtt_pw'} ne '';
    return @cmd;
}

sub mqtt_read_retained_lines {
    my ($cfg, $topic) = @_;
    my @cmd = (mqtt_cmd_base($cfg), '-v', '-C', '250', '-W', '2', '-t', $topic);
    my $pid = open my $fh, '-|', @cmd;
    return () if !$pid;
    my @lines = <$fh>;
    close $fh;
    chomp @lines;
    return @lines;
}

sub xml_escape {
    my ($s) = @_;
    $s = '' if !defined $s;
    $s =~ s/&/&amp;/g;
    $s =~ s/</&lt;/g;
    $s =~ s/>/&gt;/g;
    $s =~ s/"/&quot;/g;
    $s =~ s/'/&apos;/g;
    return $s;
}

sub title_safe {
    my ($s) = @_;
    $s = '' if !defined $s;
    $s =~ s/[^A-Za-z0-9_\-]+/_/g;
    $s =~ s/^_+|_+$//g;
    return $s || 'Node';
}

sub loxberry_ip {
    my $ips = qx(hostname -I 2>/dev/null);
    chomp $ips;
    for my $ip (split /\s+/, $ips) {
        return $ip if $ip =~ /^\d+\.\d+\.\d+\.\d+$/ && $ip !~ /^127\./;
    }
    return '127.0.0.1';
}

sub export_host {
    my ($cfg) = @_;
    my $h = trim($cfg->{'vlx2mqtt.mqtt_host'} || '127.0.0.1');
    return loxberry_ip() if $h =~ /^(?:127\.0\.0\.1|localhost|::1)$/i;
    return $h;
}

sub read_nodes_from_mqtt {
    my ($cfg) = @_;
    my $root = trim($cfg->{'vlx2mqtt.root_topic'} || 'vlx2mqtt');
    my %nodes;
    my %rain;
    my @lines = mqtt_read_retained_lines($cfg, "$root/#");
    for my $l (@lines) {
        next unless $l =~ /^\Q$root\E\/(\S+)\s*(.*)$/;
        my ($path, $payload) = ($1, $2);
        if ($path =~ /^(\d+)\/name$/) {
            $nodes{$1}{id} = $1;
            $nodes{$1}{name} = $payload;
        } elsif ($path =~ /^(\d+)\/node_id$/) {
            $nodes{$1}{id} = $payload || $1;
        } elsif ($path =~ /^name_map\/(.+)$/) {
            my $name = $1;
            my $id = $payload;
            if ($id =~ /^\d+$/) {
                $nodes{$id}{id} = $id;
                $nodes{$id}{name} = $name;
            }
        } elsif ($path =~ /^(.+)\/rain$/) {
            $rain{$1} = 1;
        }
    }
    if (!%nodes) {
        my @fallback = ('Fenster_links', 'Fenster_rechts', 'Rollladen_links', 'Rollladen_rechts');
        for my $i (0..$#fallback) {
            $nodes{$i} = { id => $i, name => $fallback[$i] };
        }
        $rain{'Fenster_links'} = 1;
        $rain{'Fenster_rechts'} = 1;
    }
    my @out;
    for my $id (sort { $a <=> $b } keys %nodes) {
        my $name = $nodes{$id}{name} || "node_$id";
        my $topic_id = (($cfg->{'vlx2mqtt.topic_identifier'} || 'name') eq 'node_id') ? $id : $name;
        push @out, { id => $id, name => $name, topic_id => $topic_id, title => title_safe($name), rain => ($rain{$topic_id} || $rain{$name} || ($name =~ /fenster/i ? 1 : 0)) };
    }
    return @out;
}

sub viu_cmd {
    my (%a) = @_;
    my $analog = $a{analog} ? 'true' : 'false';
    my $unit = xml_escape($a{unit} // '');
    return "\t<VirtualInUdpCmd Title=\"" . xml_escape($a{title}) . "\" Comment=\"\" Address=\"\" Check=\"" . xml_escape($a{check}) . "\" Signed=\"true\" Analog=\"$analog\" SourceValLow=\"0\" DestValLow=\"0\" SourceValHigh=\"100\" DestValHigh=\"100\" DefVal=\"0\" MinVal=\"-10000\" MaxVal=\"10000\" Unit=\"$unit\" HintText=\"\"/>\n";
}

sub build_viu_xml {
    my ($cfg) = @_;
    my $root = trim($cfg->{'vlx2mqtt.root_topic'} || 'vlx2mqtt');
    my $host = export_host($cfg);
    my @nodes = read_nodes_from_mqtt($cfg);
    my $x = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<VirtualInUdp HintText=\"\" Title=\"VLX2MQTT\" Comment=\"Generated by VLX2MQTT LoxBerry plugin\" Address=\"" . xml_escape($host) . "\" Port=\"11883\">\n\t<Info templateType=\"1\" minVersion=\"17000331\"/>\n";
    $x .= viu_cmd(title=>'vlx2mqtt_status', check=>"MQTT:\\i$root/status=\\i\\v", analog=>0);
    $x .= viu_cmd(title=>'vlx2mqtt_status_detail', check=>"MQTT:\\i$root/status_detail=\\i\\v", analog=>0);
    $x .= viu_cmd(title=>'vlx2mqtt_status_live', check=>"MQTT:\\i$root/status_live=\\i\\v", analog=>0);
    $x .= viu_cmd(title=>'vlx2mqtt_service_status', check=>"MQTT:\\i$root/service_status=\\i\\v", analog=>0);
    $x .= viu_cmd(title=>'vlx2mqtt_status_code', check=>"MQTT:\\i$root/status_code=\\i\\v", analog=>1, unit=>'<v>');
    $x .= viu_cmd(title=>'vlx2mqtt_status_detail_code', check=>"MQTT:\\i$root/status_detail_code=\\i\\v", analog=>1, unit=>'<v>');
    $x .= viu_cmd(title=>'vlx2mqtt_status_live_code', check=>"MQTT:\\i$root/status_live_code=\\i\\v", analog=>1, unit=>'<v>');
    $x .= viu_cmd(title=>'vlx2mqtt_service_status_code', check=>"MQTT:\\i$root/service_status_code=\\i\\v", analog=>1, unit=>'<v>');
    $x .= viu_cmd(title=>'Recovery_PowerCycleRequired', check=>"MQTT:\\i$root/recovery/powercycle_required=\\i\\v", analog=>0);
    $x .= viu_cmd(title=>'Recovery_Reason', check=>"MQTT:\\i$root/recovery/reason=\\i\\v", analog=>0);
    $x .= viu_cmd(title=>'Recovery_FailureCount', check=>"MQTT:\\i$root/recovery/failure_count=\\i\\v", analog=>1, unit=>'<v>');
    $x .= viu_cmd(title=>'Recovery_Reason_Code', check=>"MQTT:\\i$root/recovery/reason_code=\\i\\v", analog=>1, unit=>'<v>');
    $x .= viu_cmd(title=>'Recovery_State', check=>"MQTT:\\i$root/recovery/state=\\i\\v", analog=>0);
    $x .= viu_cmd(title=>'Recovery_State_Code', check=>"MQTT:\\i$root/recovery/state_code=\\i\\v", analog=>1, unit=>'<v>');
    for my $n (@nodes) {
        my $tid = $n->{topic_id};
        my $t = $n->{title};
        $x .= viu_cmd(title=>"${t}_Position", check=>"MQTT:\\i$root/$tid/position=\\i\\v", analog=>1, unit=>'<v>%');
        $x .= viu_cmd(title=>"${t}_Moving", check=>"MQTT:\\i$root/$tid/moving=\\i\\v", analog=>0);
        $x .= viu_cmd(title=>"${t}_Rain", check=>"MQTT:\\i$root/$tid/rain=\\i\\v", analog=>0) if $n->{rain};
    }
    $x .= "</VirtualInUdp>\n";
    return $x;
}

sub vo_cmd {
    my (%a) = @_;
    my $analog = $a{analog} ? 'true' : 'false';
    my $extra = $a{analog} ? ' SourceValLow="0" DestValLow="0" SourceValHigh="100" DestValHigh="100"' : '';
    return "\t<VirtualOutCmd Title=\"" . xml_escape($a{title}) . "\" Comment=\"\" CmdOnMethod=\"GET\" CmdOffMethod=\"GET\" CmdOn=\"" . xml_escape($a{on}) . "\" CmdOnHTTP=\"\" CmdOnPost=\"\" CmdOff=\"" . xml_escape($a{off} // '') . "\" CmdOffHTTP=\"\" CmdOffPost=\"\" CmdAnswer=\"\" Analog=\"$analog\" Repeat=\"0\" RepeatRate=\"0\"$extra HintText=\"\"/>\n";
}

sub build_vo_xml {
    my ($cfg) = @_;
    my $root = trim($cfg->{'vlx2mqtt.root_topic'} || 'vlx2mqtt');
    my $host = export_host($cfg);
    my @nodes = read_nodes_from_mqtt($cfg);
    my $x = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<VirtualOut HintText=\"\" Title=\"VLX2MQTT\" Comment=\"Generated by VLX2MQTT LoxBerry plugin\" Address=\"/dev/udp/" . xml_escape($host) . "/11884\" CmdInit=\"\" CloseAfterSend=\"true\" CmdSep=\";\">\n\t<Info templateType=\"3\" minVersion=\"17000331\"/>\n";
    for my $n (@nodes) {
        my $tid = $n->{topic_id};
        my $t = $n->{title};
        $x .= vo_cmd(title=>"${t}UP", on=>"publish $root/$tid/set UP", off=>"publish $root/$tid/set STOP");
        $x .= vo_cmd(title=>"${t}DOWN", on=>"publish $root/$tid/set DOWN", off=>"publish $root/$tid/set STOP");
        $x .= vo_cmd(title=>"${t}STOP", on=>"publish $root/$tid/set STOP", off=>'');
        $x .= vo_cmd(title=>"${t}SET", on=>"publish $root/$tid/set <v>", off=>'', analog=>1);
    }
    $x .= "</VirtualOut>\n";
    return $x;
}

sub build_export_readme {
    my ($cfg) = @_;
    my $root = trim($cfg->{'vlx2mqtt.root_topic'} || 'vlx2mqtt');
    my $host = export_host($cfg);
    my $tid = $cfg->{'vlx2mqtt.topic_identifier'} || 'name';
    my @nodes = read_nodes_from_mqtt($cfg);
    my $node_txt = join("\n", map { "- $_->{name} (node_id=$_->{id}, topic_id=$_->{topic_id})" } @nodes);
    return "VLX2MQTT Loxone Config Export\n==============================\n\nExport host: $host\nRoot topic:  $root\nIdentifier:  $tid\n\nIncluded files:\n- VIU_VLX2MQTT.xml: Virtual UDP Input template for values from the MQTT gateway.\n- VO_VLX2MQTT.xml: Virtual Output template for commands to the MQTT gateway.\n\nUse the *_code topics for status values in Loxone wherever possible.\n\nDetected nodes:\n$node_txt\n\nStatus code overview:\n- status_code: ok=1, error=0\n- status_detail_code/status_live_code: klf_connected=1, klf_connecting=2, klf_disconnected=3, klf_unreachable=4, unknown=99\n- service_status_code: running=1, starting=2, stopped/lost/error=0\n- recovery/state_code: idle=0, requested=1, waiting=2\n\nImport VIU_VLX2MQTT.xml as Virtual UDP Inputs and VO_VLX2MQTT.xml as Virtual Outputs.\n";
}


sub crc32_bytes {
    my ($data) = @_;
    my $crc = 0xFFFFFFFF;
    foreach my $byte (unpack('C*', $data)) {
        $crc ^= $byte;
        for (1..8) {
            if ($crc & 1) {
                $crc = (($crc >> 1) ^ 0xEDB88320) & 0xFFFFFFFF;
            } else {
                $crc = ($crc >> 1) & 0xFFFFFFFF;
            }
        }
    }
    return ($crc ^ 0xFFFFFFFF) & 0xFFFFFFFF;
}

sub dos_time_date {
    my ($sec, $min, $hour, $mday, $mon, $year) = localtime(time);
    my $dostime = (($hour & 0x1F) << 11) | (($min & 0x3F) << 5) | int(($sec & 0x3F) / 2);
    my $dosdate = ((($year + 1900 - 1980) & 0x7F) << 9) | ((($mon + 1) & 0x0F) << 5) | ($mday & 0x1F);
    return ($dostime, $dosdate);
}

sub build_zip_store {
    my (%files) = @_;
    my $zip = '';
    my $central = '';
    my ($dostime, $dosdate) = dos_time_date();
    my $offset = 0;
    my $count = 0;
    for my $name (sort keys %files) {
        my $data = Encode::encode('UTF-8', $files{$name});
        my $crc = crc32_bytes($data);
        my $size = length($data);
        my $nlen = length($name);
        my $local = pack('VvvvvvVVVvv', 0x04034b50, 20, 0, 0, $dostime, $dosdate, $crc, $size, $size, $nlen, 0) . $name . $data;
        $zip .= $local;
        $central .= pack('VvvvvvvVVVvvvvvVV', 0x02014b50, 20, 20, 0, 0, $dostime, $dosdate, $crc, $size, $size, $nlen, 0, 0, 0, 0, 0, $offset) . $name;
        $offset += length($local);
        $count++;
    }
    my $cd_offset = length($zip);
    my $cd_size = length($central);
    $zip .= $central;
    $zip .= pack('VvvvvVVv', 0x06054b50, 0, 0, $count, $count, $cd_size, $cd_offset, 0);
    return $zip;
}

sub send_download {
    my ($filename, $ctype, $content) = @_;
    print $cgi->header(-type => $ctype, -attachment => $filename, -charset => 'utf-8');
    print $content;
    exit;
}

sub send_zip_download {
    my ($cfg) = @_;
    my %files = (
        'VIU_VLX2MQTT.xml' => build_viu_xml($cfg),
        'VO_VLX2MQTT.xml' => build_vo_xml($cfg),
        'README_Loxone_Export.txt' => build_export_readme($cfg),
    );
    my $data = build_zip_store(%files);
    print $cgi->header(-type => 'application/zip', -attachment => 'VLX2MQTT_Loxone_Templates.zip');
    binmode STDOUT;
    print $data;
    exit;
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
    return 'CFG.INVALID_EVENT_MONITOR_INTERVAL'
        unless $cfg->{'vlx2mqtt.event_monitor_interval'} =~ /^\d+$/
            && $cfg->{'vlx2mqtt.event_monitor_interval'} >= 30;
    return 'CFG.INVALID_EVENT_STALE_WARN_SECONDS'
        unless $cfg->{'vlx2mqtt.event_stale_warn_seconds'} =~ /^\d+$/
            && $cfg->{'vlx2mqtt.event_stale_warn_seconds'} >= 60;

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
my $doc_link = 'https://github.com/5iggi/vlx2mqtt/blob/main/docs/README.md';

if ($download) {
    if (check_pin_if_supplied()) {
        json_out({ error => 1, message => 'Invalid PIN' });
    }
    if ($download eq 'loxone_viu') {
        send_download('VIU_VLX2MQTT.xml', 'application/xml', build_viu_xml($cfg));
    } elsif ($download eq 'loxone_vo') {
        send_download('VO_VLX2MQTT.xml', 'application/xml', build_vo_xml($cfg));
    } elsif ($download eq 'loxone_readme') {
        send_download('README_Loxone_Export.txt', 'text/plain', build_export_readme($cfg));
    } elsif ($download eq 'loxone_zip') {
        send_zip_download($cfg);
    } else {
        json_out({ error => 1, message => 'Unknown download' });
    }
}

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
    $newcfg{'vlx2mqtt.event_monitor_interval'} = trim($cgi->param('event_monitor_interval'));
    $newcfg{'vlx2mqtt.event_stale_warn_seconds'} = trim($cgi->param('event_stale_warn_seconds'));
    $newcfg{'vlx2mqtt.external_recovery_enabled'} = bool_param('external_recovery_enabled');
    $newcfg{'vlx2mqtt.external_recovery_threshold'} = trim($cgi->param('external_recovery_threshold'));
    $newcfg{'vlx2mqtt.external_recovery_cooldown'} = trim($cgi->param('external_recovery_cooldown'));
    $newcfg{'vlx2mqtt.external_recovery_grace'} = trim($cgi->param('external_recovery_grace'));
    $newcfg{'vlx2mqtt.external_recovery_topic'} =
        trim($cgi->param('external_recovery_topic')) || 'vlx2mqtt/recovery/powercycle_required';
    $newcfg{'vlx2mqtt.preventive_recovery_hours'} = trim($cgi->param('preventive_recovery_hours'));

    my $validation_error = validate_config(\%newcfg);
    if ($validation_error) {
        my %validation_fallback = (
            'CFG.INVALID_EVENT_MONITOR_INTERVAL' => 'Event monitor interval must be an integer >= 30 seconds',
            'CFG.INVALID_EVENT_STALE_WARN_SECONDS' => 'Event stale warning threshold must be an integer >= 60 seconds',
        );
        $notice = lang($validation_error, $validation_fallback{$validation_error} // $validation_error);
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
    LBOX_EXPORT_HOST                    => export_host($cfg),
    LBOX_VIU_PORT                       => '11883',
    LBOX_VO_PORT                        => '11884',
    LBOX_ROOT_TOPIC                     => maybe_unmangle($cfg->{'vlx2mqtt.root_topic'} || 'vlx2mqtt'),
    LBOX_TOPIC_IDENTIFIER               => maybe_unmangle($cfg->{'vlx2mqtt.topic_identifier'} || 'name'),
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
    event_monitor_interval             => maybe_unmangle($cfg->{'vlx2mqtt.event_monitor_interval'} || '60'),
    event_stale_warn_seconds            => maybe_unmangle($cfg->{'vlx2mqtt.event_stale_warn_seconds'} || '900'),
    ICON_SRC                            => get_plugin_icon(128) || '/system/images/icons/vlx2mqtt/icon.svg',
);

my $plugintitle  = 'VLX2MQTT KLF200 Bridge';
my $helplink     = $doc_link;
my $helptemplate = 'help.html';

LoxBerry::Web::lbheader($plugintitle, $helplink, $helptemplate);
print $template->output();
LoxBerry::Web::lbfooter();
``