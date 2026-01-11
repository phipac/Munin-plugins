#!/usr/bin/python3

import collections
from geopy.distance import geodesic
import json
import os
import sys

# --- Configuration begins ---
DATA_SOURCES = {
    '1090': '/run/dump1090-fa',
    '978': '/run/skyaware978' 
}

ALT_HIST = 4500  # Altitude change threshold for asc/des
# --- Configuration ends ---

CONFIG = {
    'ac': """\
multigraph adsb_ac_n
graph_title ADS-B/UAT Aircraft Count
graph_category adsb
graph_vlabel count
n.label Total Unique Aircraft
n_1090.label 1090ES (ADS-B)
n_978.label 978 (UAT)
n_pos.label With Position
n_des.label Descending
n_lvl.label Level
n_asc.label Ascending

multigraph adsb_ac_range
graph_title ADS-B/UAT Max Range
graph_category adsb
graph_vlabel nm
max_range.label Maximum Distance
avg_range.label Average Distance
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
""",
    'signal': """\
graph_title ADS-B/UAT Peak Signal
graph_category adsb
graph_vlabel dBFS
peak_1090.label 1090 Peak
peak_978.label 978 Peak
noise_1090.label 1090 Noise
noise_978.label 978 Noise
"""
}

def get_json(path, filename):
    try:
        with open(os.path.join(path, filename)) as f:
            return json.load(f)
    except: return None

def do_config(which):
    print(CONFIG.get(which, "graph_title ADS-B Unknown\n"), end='')
    sys.exit(0)

def do_fetch(which):
    if which == 'ac':
        ac_all = set()
        ac_1090 = set()
        ac_978 = set()
        ac_n_pos = collections.defaultdict(lambda: {'alt_s': None, 'alt_e': None})
        dist = []
        
        main_rx = get_json(DATA_SOURCES['1090'], 'receiver.json')
        rx_pos = (main_rx['lat'], main_rx['lon']) if main_rx else (0,0)

        for tech, path in DATA_SOURCES.items():
            recv = get_json(path, 'receiver.json')
            if not recv: continue
            
            n_hist = int(recv.get('history', 0))
            for i in range(n_hist):
                d = get_json(path, f'history_{i}.json')
                if d:
                    for ac in d['aircraft']:
                        hex_id = ac['hex']
                        ac_all.add(hex_id)
                        if tech == '1090': ac_1090.add(hex_id)
                        else: ac_978.add(hex_id)

                        alt = ac.get('alt_baro') or ac.get('alt_geom') or 0
                        if 'lat' in ac and 'lon' in ac:
                            if alt == 'ground': alt = 0
                            if ac_n_pos[hex_id]['alt_s'] is None:
                                ac_n_pos[hex_id]['alt_s'] = alt
                            ac_n_pos[hex_id]['alt_e'] = alt
                            try:
                                dist.append(geodesic(rx_pos, (ac['lat'], ac['lon'])).nm)
                            except: continue

        alt_asc = alt_des = alt_lvl = 0
        for alts in ac_n_pos.values():
            try:
                diff = int(alts['alt_e']) - int(alts['alt_s'])
                if diff > ALT_HIST: alt_asc += 1
                elif diff < -ALT_HIST: alt_des += 1
                else: alt_lvl += 1
            except: alt_lvl += 1

        print('multigraph adsb_ac_n')
        print(f'n.value {len(ac_all)}\nn_1090.value {len(ac_1090)}\nn_978.value {len(ac_978)}')
        print(f'n_pos.value {len(ac_n_pos)}\nn_asc.value {alt_asc}\nn_lvl.value {alt_lvl}\nn_des.value {alt_des}')
        print('multigraph adsb_ac_range')
        print(f'avg_range.value {sum(dist)/max(len(dist),1):.1f}\nmax_range.value {max(dist) if dist else 0:.1f}')

    elif which == 'messages':
        for tech, path in DATA_SOURCES.items():
            s = get_json(path, 'stats.json')
            if s:
                # dump1090/978 use 'accepted' array for message counts
                msg_count = s['last5min']['local']['accepted'][0]
                print(f"msg_{tech}.value {msg_count / 300.0:.1f}")

    elif which == 'cpu':
        for tech, path in DATA_SOURCES.items():
            s = get_json(path, 'stats.json')
            if s:
                cpu = s['last5min']['cpu']
                val = (cpu['demod'] + cpu['reader'] + cpu['background']) / 3000.0
                print(f"cpu_{tech}.value {val:.3f}")

    elif which == 'signal':
        for tech, path in DATA_SOURCES.items():
            s = get_json(path, 'stats.json')
            if s:
                print(f"peak_{tech}.value {s['last5min']['local']['peak_signal']:.1f}")
                print(f"noise_{tech}.value {s['last5min']['local']['noise']:.1f}")

if __name__ == '__main__':
    name = os.path.basename(sys.argv[0])
    metric = name.split('_')[-1]
    if len(sys.argv) > 1 and sys.argv[1] == 'config':
        do_config(metric)
    else:
        do_fetch(metric)
