#!/usr/bin/python3
import json
import urllib.request
import sys

# Update these to your local paths
DATA_SOURCES = {
    '1090': 'http://localhost/dump1090-fa/',
    '978': 'http://localhost/skyaware978/'
}

def get_json(base_url, file):
    try:
        with urllib.request.urlopen(base_url + file) as url:
            return json.loads(url.read().decode())
    except:
        return None

# --- Configuration with Improved Scaling ---
CONFIGS = {
    'ac': """\
graph_title ADS-B/UAT Aircraft
graph_category adsb
graph_vlabel count
n_air.label Airborne
n_air.draw AREA
n_gnd.label Ground
n_gnd.draw STACK
n_pos.label With Position
n_pos.draw LINE2""",

    'health': """\
graph_title ADS-B Signal Health
graph_category adsb
graph_vlabel dBFS
graph_args --upper-limit 0 --lower-limit -60
peak.label Peak Signal
noise.label Noise Floor
noise.draw LINE2""",

    'msgs': """\
graph_title ADS-B Message Rates
graph_category adsb
graph_vlabel msgs/sec
m_1090.label 1090MHz
m_978.label 978MHz (UAT)
m_978.draw LINE2"""
}

def do_config(which):
    print(CONFIGS[which])

def do_fetch(which):
    if which == 'ac':
        a = get_json(DATA_SOURCES['1090'], 'aircraft.json')
        if a:
            # Count logic
            air = sum(1 for x in a['aircraft'] if x.get('altitude') != 'ground')
            gnd = sum(1 for x in a['aircraft'] if x.get('altitude') == 'ground')
            pos = sum(1 for x in a['aircraft'] if 'lat' in x)
            print(f"n_air.value {air}\nn_gnd.value {gnd}\nn_pos.value {pos}")
            
    elif which == 'health':
        s = get_json(DATA_SOURCES['1090'], 'stats.json')
        if s and 'last5min' in s:
            sig = s['last5min'].get('local', {})
            print(f"peak.value {sig.get('peak_signal', 'U')}")
            print(f"noise.value {sig.get('noise', 'U')}")

    elif which == 'msgs':
        s1090 = get_json(DATA_SOURCES['1090'], 'stats.json')
        s978 = get_json(DATA_SOURCES['978'], 'stats.json')
        v1090 = s1090['last5min']['local']['accepted'][0] / 300 if s1090 else "U"
        v978 = s978['last5min']['local']['accepted'][0] / 300 if s978 else "U"
        print(f"m_1090.value {v1090}\nm_978.value {v978}")

if __name__ == "__main__":
    metric = sys.argv[0].split('_')[-1]
    if len(sys.argv) > 1 and sys.argv[1] == 'config':
        do_config(metric)
    else:
        do_fetch(metric)
