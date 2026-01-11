#!/usr/bin/python3

# dump1090 statistics plugin for Munin
# Updated for Python 3 and Geopy 2.x
# Original Copyright (c) 2017 David King
# https://github.com/strix-technica/ADSB-tools

import collections
from geopy.distance import geodesic
import json
import os
import sys

KM_PER_FT = 0.0003048

# --- Configuration begins ---
RX_ALT_KM = KM_PER_FT * 108 # feet

# Adjust this path if your dump1090-mutability/fa data is elsewhere
JSON_DATA = '/run/dump1090-fa'
STATS_FILE = os.path.join(JSON_DATA, 'stats.json')
RECVR_FILE = os.path.join(JSON_DATA, 'receiver.json')

# altitude hysteresis: a/c are level if alt difference < +- ALT_HIST
# Set fairly high to distinguish between FL changes and departure/arrivals
ALT_HIST = 4500
# --- Configuration ends ---

CONFIG = {
    'ac': """\
multigraph dump1090_ac_n
graph_title ADS-B aircraft count
graph_category dump1090
graph_vlabel count

n.label Aircraft count
n_pos.label Aircraft (with position) count
n_des.label Aircraft descending
n_des.draw LINESTACK1
n_lvl.label Aircraft level
n_lvl.draw LINESTACK1
n_asc.label Aircraft ascending
n_asc.draw LINESTACK1

multigraph dump1090_ac_n_pct
graph_title ADS-B aircraft altitude change
graph_category dump1090
graph_vlabel %
graph_order n_des=dump1090_ac_n.n_des n_asc=dump1090_ac_n.n_asc n_lvl=dump1090_ac_n.n_lvl n_pos=dump1090_ac_n.n_pos

p_des.label Aircraft descending
p_des.cdef n_des,n_pos,/,100,*
p_des.draw AREA
p_lvl.label Aircraft level
p_lvl.cdef n_lvl,n_pos,/,100,*
p_lvl.draw STACK
p_asc.label Aircraft ascending
p_asc.cdef n_asc,n_pos,/,100,*
p_asc.draw STACK
n_des.graph no
n_asc.graph no
n_lvl.graph no
n_pos.graph no

multigraph dump1090_ac_range
graph_title ADS-B aircraft distance
graph_category dump1090
graph_vlabel nm

avg_range.label Average distance
max_range.label Maximum distance
""",
    'cpu': """\
graph_title ADS-B CPU utilisation
graph_category dump1090
graph_vlabel %

usb.label USB wait
usb.draw LINESTACK1
bg.label Network I/O
bg.draw LINESTACK1
demod.label Demodulation
demod.draw LINESTACK1
""",
    'messages': """\
graph_title ADS-B message count
graph_category dump1090
graph_vlabel messages/second

good0.label Good Mode S messages
good0.draw LINESTACK1
good1.label Good Mode S messages (1 bit error)
good1.draw LINESTACK1
good2.label Good Mode S messages (2 bit error)
good2.draw LINESTACK1
""",
    'quality': """\
graph_title ADS-B signal quality problems
graph_category dump1090
graph_vlabel %
graph_order bad unknown good sp_track
graph_args -A -l 0

bad.label Bad Mode-S messages
bad.draw AREA
unknown.label Unknown Mode-S messages
unknown.draw STACK
good.label Good Mode-S messages
good.draw STACK
sp_track.label Single-point tracks
sp_track.draw LINE1
""",
    'signal': """\
graph_title ADS-B signal strength
graph_category dump1090
graph_vlabel dBFS

mean.label Mean signal strength
peak.label Peak signal strength
noise.label Noise floor
mean_snr.label Mean signal SNR
mean_snr.cdef mean,noise,-
mean_snr.colour 330099
peak_snr.label Peak signal SNR
peak_snr.cdef peak,noise,-
peak_snr.colour 440057
""",
    'tracks': """\
graph_title ADS-B track count
graph_category dump1090
graph_vlabel count

total.label Total tracks
single.label Single-point tracks
""",
}


def do_config(which):
    """Output Munin config data"""
    print(CONFIG[which], end='')
    sys.exit(0)


def do_fetch(which):
    """Output recorded Munin data"""
    if which == 'ac':
        with open(RECVR_FILE) as f:
            receiver = json.load(f)
        n_hist = int(receiver['history'])
        # geodesic doesn't use altitude well in simple distance calcs, so we use lat/lon
        rx_pos = (receiver['lat'], receiver['lon'])

        data = []
        for i in range(n_hist):
            fn = os.path.join(JSON_DATA, 'history_%s.json' % (i,))
            if os.path.exists(fn):
                with open(fn) as f:
                    d = json.load(f)
                data.append((d['now'], d['aircraft']))
        data.sort()

        ac_n = set()
        ac_n_pos = collections.defaultdict(lambda: {'alt_s': None, 'alt_e': None})
        dist = []

        for ts, d in data[-10:]:
            for ac in d:
                ac_n.add(ac['hex'])
                # Some versions use 'alt_baro' or 'alt_geom', ensuring fallback here
                alt = ac.get('nav_altitude_mcp') or ac.get('alt_baro') or 0

                if 'lat' in ac and 'lon' in ac:
                    if alt == 'ground':
                        alt = 0
                    if ac_n_pos[ac['hex']]['alt_s'] is None:
                        ac_n_pos[ac['hex']]['alt_s'] = alt
                    ac_n_pos[ac['hex']]['alt_e'] = alt

                    try:
                        # Geodesic calculation (replaces vincenty)
                        d_val = geodesic(rx_pos, (ac['lat'], ac['lon'])).nm
                        dist.append(d_val)
                    except (TypeError, ValueError) as e:
                        print(f"Distance calc error: {e}", file=sys.stderr)
                        continue

        avg_dist = sum(dist) / max(len(dist), 1)
        max_dist = max(dist) if dist else 0
        alt_asc = alt_des = alt_lvl = 0

        for alts in ac_n_pos.values():
            try:
                diff = int(alts['alt_e']) - int(alts['alt_s'])
                if diff > ALT_HIST:
                    alt_asc += 1
                elif diff < -ALT_HIST:
                    alt_des += 1
                else:
                    alt_lvl += 1
            except (TypeError, ValueError):
                alt_lvl += 1

        print('multigraph dump1090_ac_n')
        print(f'n.value {len(ac_n)}')
        print(f'n_pos.value {len(ac_n_pos)}')
        print(f'n_asc.value {alt_asc}')
        print(f'n_lvl.value {alt_lvl}')
        print(f'n_des.value {alt_des}')

        print('multigraph dump1090_ac_range')
        print(f'avg_range.value {avg_dist:.1f}')
        print(f'max_range.value {max_dist:.1f}')
        return

    # Non-AC metrics (CPU, Messages, etc)
    with open(STATS_FILE) as f:
        stats_data = json.load(f)['last5min']

    if which == 'cpu':
        print(f"usb.value {stats_data['cpu']['reader'] / 3000.0:.3f}")
        print(f"demod.value {stats_data['cpu']['demod'] / 3000.0:.3f}")
        print(f"bg.value {stats_data['cpu']['background'] / 3000.0:.3f}")

    elif which == 'messages':
        accepted = stats_data['local']['accepted']
        # Pad list if version of dump1090 provides fewer than 3 indices
        while len(accepted) < 3: accepted.append(0)
        print(f"good0.value {accepted[0] / 300.0:.1f}")
        print(f"good1.value {accepted[1] / 300.0:.1f}")
        print(f"good2.value {accepted[2] / 300.0:.1f}")

    elif which == 'quality':
        total = float(stats_data['local']['modes'])
        if total > 0:
            print(f"bad.value {(stats_data['local']['bad'] / total * 100):.3f}")
            print(f"unknown.value {(stats_data['local']['unknown_icao'] / total * 100):.3f}")
            print(f"good.value {(sum(stats_data['local']['accepted']) / total * 100):.3f}")

        track_total = float(stats_data['tracks']['all'])
        if track_total > 0:
            print(f"sp_track.value {(stats_data['tracks']['single_message'] / track_total * 100):.3f}")

    elif which == 'signal':
        print(f"mean.value {stats_data['local']['signal']:.1f}")
        print(f"peak.value {stats_data['local']['peak_signal']:.1f}")
        print(f"noise.value {stats_data['local']['noise']:.1f}")

    elif which == 'tracks':
        print(f"total.value {stats_data['tracks']['all']:.1f}")
        print(f"single.value {stats_data['tracks']['single_message']:.1f}")


if __name__ == '__main__':
    # Munin wildcard logic: extract 'messages' from 'dump1090_messages'
    plugin_name = os.path.basename(sys.argv[0])
    try:
        which_metric = plugin_name.rsplit('_', 1)[1]
    except IndexError:
        print("Plugin must be run via a symlink (e.g., dump1090_ac)", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) == 2 and sys.argv[1] == 'config':
        do_config(which_metric)
    else:
        do_fetch(which_metric)
