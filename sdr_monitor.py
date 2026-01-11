#!/usr/bin/python3
import os
import sys
import subprocess

# --- Config ---
# SDRTrunk runs on Java. We'll track all Java processes.
PROCESS_NAME = "java"

def get_resources():
    """Fetch CPU and RAM for the SDRTrunk Java process."""
    try:
        cmd = f"ps -C {PROCESS_NAME} -o %cpu,rss --no-headers"
        lines = os.popen(cmd).read().strip().split('\n')
        cpu = sum(float(l.split()[0]) for l in lines if l.strip())
        mem = sum(float(l.split()[1]) for l in lines if l.strip()) / 1024.0 # KB to MB
        return cpu, mem
    except:
        return 0, 0

def get_usb_stability():
    """Scrape dmesg for SDR-specific hardware issues and power sags."""
    # Count disconnects and driver-level resubmit errors
    cmd_disc = "dmesg | grep -Ei 'usb|rtl|airspy' | grep -Ei 'disconnect|reconnecting|resubmit|failed' | wc -l"
    # Count specific power/voltage warnings (babble, over-current, VBUS)
    cmd_pwr = "dmesg | grep -Ei 'over-current|power-off|vbus|babble|insufficient' | wc -l"
    
    try:
        disc = subprocess.check_output(cmd_disc, shell=True).decode().strip()
        pwr = subprocess.check_output(cmd_pwr, shell=True).decode().strip()
        return disc, pwr
    except:
        return 0, 0

# --- Munin Plugin Logic ---
name = os.path.basename(sys.argv[0])
metric = name.split('_')[-1]

if len(sys.argv) > 1 and sys.argv[1] == 'config':
    if metric == 'resources':
        print("graph_title SDRTrunk Resource Usage")
        print("graph_category radio")
        print("graph_vlabel % / MB")
        print("cpu.label Java CPU Usage (%)")
        print("mem.label Java RAM Usage (MB)")
    elif metric == 'usb':
        print("graph_title SDR USB Power & Stability")
        print("graph_category radio")
        print("graph_vlabel events")
        print("disconnects.label Bus Resets/Disconnects")
        print("disconnects.type DERIVE")
        print("disconnects.min 0")
        print("power_err.label Power/Voltage Events")
        print("power_err.type DERIVE")
        print("power_err.min 0")
    sys.exit(0)

cpu, mem = get_resources()
disc, pwr = get_usb_stability()

if metric == 'resources':
    print(f"cpu.value {cpu}")
    print(f"mem.value {mem}")
elif metric == 'usb':
    print(f"disconnects.value {disc}")
    print(f"power_err.value {pwr}")
