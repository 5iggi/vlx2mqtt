#!/usr/bin/perl
use strict;
use warnings;
use utf8;
use open qw(:std :encoding(UTF-8));
use File::Path qw(make_path);

my $python = shift @ARGV;
if (!$python || !@ARGV) {
    die "Usage: vlx2mqtt_daemon.pl <python> <vlx2mqtt.py> [config]\n";
}

my $logdir = '/opt/loxberry/log/plugins/vlx2mqtt';
make_path($logdir) if !-d $logdir;

# Keep daemon startup lean. Log registration is done during postinstall/postroot.
exec $python, @ARGV;
die "Could not exec VLX2MQTT daemon: $!\n";
