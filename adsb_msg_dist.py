#!/usr/bin/python3
# encoding: utf-8

# ADS-B message distribution analysis plugin for Munin
# Updated for Python 3 and Geopy 2.x
# Original Copyright (c) 2017 David King

import collections
import csv
import datetime
from geopy.distance import geodesic
import logging
import logging.handlers
import math
import queue  # Renamed from Queue in Python 3
import os
import socket
import sys
import threading
import time

# --- Configuration begins ---
SERVER = '127.0.0.1'
PORT   = 30003
TIMER  = 300

LOG_FILE = '/var/log/adsb-msg-dist.log'
STATS_FILE = '/var/run/adsb-msg-dist.dat'
PID_FILE = '/var/run/adsb-msg-dist.pid'

USER   = 'munin' # for daemon mode
GROUP  = 'adm'

# Messages older than this will be ignored
AC_TO_SECS = 600
# --- Configuration ends ---

HDR = ['type', 'subtype', 'sid', 'aid', 'icao', 'fid', 'g_date', 'g_time', 'l_date', 'l_time', 'cs', 'alt', 'gs', 'trk', 'lat', 'lon', 'vr', 'squawk', 'sq_flag', 'emerg', 'ident', 'gnd']
KM_PER_FT = 0.0003048

class Message(object):
    """ADS-B message class (subset)"""
    def __init__(self, d):
        # Python 3 strptime works identically
        self.ts = datetime.datetime.strptime(d['g_date'] + d['g_time'] + '000',
                                              '%Y/%m/%d%H:%M:%S.%f')
        self.icao = d['icao']
        self.lat = self.lon = self.alt = self.gs = None

        if d['lat']:
            self.lat = float(d['lat'])
        if d['lon']:
            self.lon = float(d['lon'])
        if d['alt']:
            self.alt = float(d['alt']) * KM_PER_FT
        if d['gs']:
            self.gs = int(d['gs'])

    @property
    def pos(self):
        if self.lat is not None and self.lon is not None:
            return (self.lat, self.lon)
        return None

    def __str__(self):
        return "{}: {} → {}° {}° {}' @ {} kts".format(
                self.ts.strftime('%H:%M:%S.%f'),
                self.icao,
                self.lat if self.lat else '-',
                self.lon if self.lon else '-',
                (self.alt / KM_PER_FT) if self.alt else '-',
                self.gs if self.gs else '-')

    def __repr__(self):
        return self.__str__()


class StreamToLogger(object):
    """Fake file-like stream object that redirects writes to a logger instance."""
    def __init__(self, logger, handler, log_level=logging.INFO):
        self.logger = logger
        self.handler = handler
        self.log_level = log_level

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self):
        pass

    def fileno(self):
        return self.handler.stream.fileno()


def init_socket():
    """(Re)acquire TCP connection. Returns a CSV reader."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while run:
        try:
            s.connect((SERVER, PORT))
            break
        except socket.error as e:
            logger.info('waiting for %s:%s - %s' % (SERVER, PORT, e))
            time.sleep(5)
    logger.info('(re)connected to %s:%s' % (SERVER, PORT))
    # Python 3: makefile needs mode='r' and encoding for csv.reader
    return csv.reader(s.makefile(mode='r', encoding='utf-8', newline=''))


def mean_sd(data):
    """Returns a tuple of (mean, sample_std_deviation)"""
    if not data:
        return (0.0, 0.0)
    n = len(data)
    mean = sum(data) / n
    ssd = math.sqrt(sum((x - mean)**2 for x in data) / n)
    return (mean, ssd)


run = True
msgs = queue.Queue()

def input_thread_entrypoint():
    """Relays messages via queue `msgs`."""
    while run:
        try:
            reader = init_socket()
            for row in reader:
                if not run: return
                d = dict(zip(HDR, row))
                if d.get('type') == 'MSG' and d.get('subtype') in ['3', '4']:
                    msgs.put(Message(d))
        except Exception as e:
            logger.error(f"Socket error: {e}")
            time.sleep(2)

def do_ts(last, delta, msg):
    d = msg.ts - last[msg.icao]['ts']
    delta['ts'].append(d.total_seconds())

def do_pos(last, delta, msg):
    # Geodesic calculation
    d = geodesic(last[msg.icao]['pos'], msg.pos).nm
    nm_per_sec = last[msg.icao]['gs'] / 3600.0
    if nm_per_sec > 0:
        delta['pos'].append(d / nm_per_sec)

def mainline_entrypoint():
    last = collections.defaultdict(lambda: {'ts': None, 'pos': None, 'gs': None})
    ac_timeout = datetime.timedelta(seconds=AC_TO_SECS)

    while run:
        delta = {'ts': [], 'pos': []}
        time.sleep(TIMER - time.time() % TIMER)

        n = msgs.qsize()
        for _ in range(n):
            msg = msgs.get()

            # Logic check for contiguous track
            if (last[msg.icao]['pos'] and
                last[msg.icao]['gs'] and
                (last[msg.icao]['ts'] > (datetime.datetime.now() - ac_timeout)) and
                msg.pos):

                do_ts(last, delta, msg)
                do_pos(last, delta, msg)

            if msg.pos:
                last[msg.icao]['pos'] = msg.pos
                last[msg.icao]['ts'] = msg.ts
            if msg.gs:
                last[msg.icao]['gs'] = msg.gs

        ts_mean, ts_sd = mean_sd(delta['ts'])
        pos_mean, pos_sd = mean_sd(delta['pos'])

        try:
            with open(STATS_FILE, 'w') as f:
                f.write(f"ts_sd.value {ts_sd}\n")
                f.write(f"ts_mean.value {ts_mean}\n")
                f.write(f"ts_n.value {len(delta['ts'])}\n")
                f.write(f"pos_sd.value {pos_sd}\n")
                f.write(f"pos_mean.value {pos_mean}\n")
                f.write(f"pos_n.value {len(delta['pos'])}\n")
        except Exception as e:
            logger.error(f"Failed to write stats: {e}")


def munin_config():
    print("""graph_title ADS-B message distribution
graph_vlabel sec, 1 sec displacement ratio
graph_category adsb
graph_info This graph characterises the quality of reception. A small s.d. indicates you're receiving most messages.
ts_sd.label S.d. time interval
ts_mean.label Mean time interval
ts_n.label ts sample size
pos_sd.label S.d. normalised displacement ratio
pos_mean.label Mean normalised displacement ratio
pos_n.label pos sample size""")
    sys.exit(0)

def munin_data():
    if not os.path.isfile(STATS_FILE):
        print(f'stats file {STATS_FILE} missing')
        sys.exit(1)
    try:
        with open(STATS_FILE) as f:
            print(f.read(), end='')
    except OSError:
        pass
    sys.exit(0)

def do_collector():
    global run
    input_thread = threading.Thread(target=input_thread_entrypoint, daemon=True)
    input_thread.start()
    try:
        mainline_entrypoint()
    except KeyboardInterrupt:
        run = False

def do_daemon(stdout=None, stderr=None):
    # Basic daemonization for Python 3
    # Note: requires 'python3-daemon' package
    import daemon
    from daemon import pidfile
    import grp
    import pwd
    import signal

    uid = pwd.getpwnam(USER).pw_uid
    gid = grp.getgrnam(GROUP).gr_gid

    context = daemon.DaemonContext(
        working_directory='/tmp',
        umask=0o022, # Python 3 octal syntax
        uid=uid,
        gid=gid,
        pidfile=pidfile.TimeoutPIDLockFile(PID_FILE),
        stdout=stdout,
        stderr=stderr
    )

    with context:
        do_collector()

# --- Entry Point ---
logger = logging.getLogger('adsb-msg-dist')
logger.setLevel(logging.INFO)
log_fmt = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')

if len(sys.argv) == 2 and sys.argv[1] == 'config':
    munin_config()
elif len(sys.argv) == 1:
    munin_data()
elif len(sys.argv) == 2 and sys.argv[1] == 'fg':
    sh = logging.StreamHandler()
    sh.setFormatter(log_fmt)
    logger.addHandler(sh)
    do_collector()
elif len(sys.argv) == 2 and sys.argv[1] == 'daemon':
    fh = logging.handlers.WatchedFileHandler(LOG_FILE)
    fh.setFormatter(log_fmt)
    logger.addHandler(fh)
    do_daemon(stdout=StreamToLogger(logger, fh, logging.INFO),
              stderr=StreamToLogger(logger, fh, logging.ERROR))
else:
    print(f'Usage: {sys.argv[0]} [config|fg|daemon]')
