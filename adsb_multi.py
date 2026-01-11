#!/usr/bin/python3

import collections
from geopy.distance import geodesic
import json
import os
import sys

# --- Configuration ---
DATA_SOURCES = {
    '1090': '/run/dump1090-fa',
    '978': '/run/skyaware978'
}

CONFIG = {
    'ac': """\
multigraph adsb_ac_n
graph_title ADS-B/UAT Traffic Categories
graph_category adsb
graph_vlabel count
n.label Total Unique
n_pos.label With Position
n_air.label Airborne
n_gnd.label Ground Vehicles/Taxi

multigraph adsb_ac_uat_meta
graph_title UAT (978) Service Metadata
graph_category adsb
graph_vlabel count
tis_b.label TIS-B Traffic Rebroadcasts
anon.label Anonymous Mode (UOP)

multigraph adsb_ac_range
graph_title ADS-B/UAT Max Range
graph_category adsb
graph_vlabel nm
max_range.label Maximum Distance
avg_range.label Average Distance
""",
    'health': """\
multigraph adsb_health_signal
graph_title ADS-B (1090) Signal Integrity
graph_category adsb
graph_vlabel messages
accepted.label Valid Messages
fixed.label CRC Fixed
dropped.label Dropped (Bad CRC)

multigraph adsb_health_noise
graph_title ADS-B (1090) Signal-to-Noise
graph_category adsb
graph_vlabel dBFS
peak.label Peak Signal
noise.label Noise Floor
""",
    'messages': """\
graph_title ADS-B/UAT Message Rate
graph_category adsb
graph_vlabel msg/sec
msg_1090.label 1090ES Messages
msg_978.label UAT Messages
""",
    'cpu': """\
graph_title ADS-B/UAT CPU Utilisation
graph_category adsb
graph_vlabel %
cpu_1090.label dump1090-fa
cpu_978.label dump978-fa
"""
}

def get_json(path, filename):
    try:
        with open(os.path.join(path, filename)) as f:
            return json.load(f)
    except: return None

def do_fetch(which):
    if which == 'ac':
        ac_all = set()
        n_pos, n_air, n_gnd = 0, 0, 0
        tis_b, anon = 0, 0
        dist = []

        main_rx = get_json(DATA_SOURCES['1090'], 'receiver.json')
        rx_pos = (main_rx['lat'], main_rx['lon']) if main_rx and 'lat' in main_rx else (0,0)

        for tech, path in DATA_SOURCES.items():
            recv = get_json(path, 'receiver.json')
            if not recv: continue
            for i in range(int(recv.get('history', 0))):
                d = get_json(path, f'history_{i}.json')
                if d:
                    for ac in d['aircraft']:
                        if ac['hex'] not in ac_all:
                            ac_all.add(ac['hex'])
                            if 'lat' in ac:
                                n_pos += 1
                                if rx_pos != (0,0):
                                    try: dist.append(geodesic(rx_pos, (ac['lat'], ac['lon'])).nm)
                                    except: pass
                            if ac.get('alt_baro') == 'ground': n_gnd += 1
                            else: n_air += 1
                            if tech == '978':
                                if ac.get('addr_type') == 1: anon += 1
                                if 'tisb' in ac.get('type', ''): tis_b += 1

        print('multigraph adsb_ac_n')
        print(f'n.value {len(ac_all)}\nn_pos.value {n_pos}\nn_air.value {n_air}\nn_gnd.value {n_gnd}')
        print('multigraph adsb_ac_uat_meta')
        print(f'tis_b.value {tis_b}\nanon.value {anon}')
        print('multigraph adsb_ac_range')
        print(f'avg_range.value {sum(dist)/max(len(dist),1):.1f}\nmax_range.value {max(dist) if dist else 0:.1f}')

    elif which == 'health':
        s1090 = get_json(DATA_SOURCES['1090'], 'stats.json')
        if s1090 and 'last5min' in s1090:
            loc = s1090['last5min'].get('local', {})
            crc_fixed = loc.get('fixed', 0) or loc.get('strong', 0)
            print('multigraph adsb_health_signal')
            print(f"accepted.value {sum(loc.get('accepted', [0]))}\nfixed.value {crc_fixed}\ndropped.value {loc.get('bad', 0)}")
            print('multigraph adsb_health_noise')
            print(f"peak.value {loc.get('peak_signal', 'U')}\nnoise.value {loc.get('noise', 'U')}")

    elif which == 'messages':
        for tech, path in DATA_SOURCES.items():
            s = get_json(path, 'stats.json')
            # If UAT stats.json is missing, it will pull from the message count in aircraft.json
            if s:
                val = (s['last5min']['local']['accepted'][0] / 300.0)
            else:
                ac = get_json(path, 'aircraft.json')
                val = ac.get('messages', 'U') if ac else 'U'
            print(f"msg_{tech}.value {val}")

    elif which == 'cpu':
        for tech, path in DATA_SOURCES.items():
            s = get_json(path, 'stats.json')
            if s and 'last5min' in s:
                cpu = s['last5min']['cpu']
                val = (cpu['demod'] + cpu['reader'] + cpu['background']) / 3000.0
                print(f"cpu_{tech}.value {val:.3f}")
            else: print(f"cpu_{tech}.value U")

if __name__ == '__main__':
    name = os.path.basename(sys.argv[0])
    metric = name.split('_')[-1]
    if len(sys.argv) > 1 and sys.argv[1] == 'config':
        print(CONFIG.get(metric, "graph_title Unknown\n"))
    else:
        do_fetch(metric)
