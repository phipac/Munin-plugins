#!/usr/bin/python3
import os
import sys
import subprocess

PROCESS_NAME = "java"

def get_stats():
    # Resource Stats
    try:
        cmd = f"ps -C {PROCESS_NAME} -o %cpu,rss --no-headers"
        lines = os.popen(cmd).read().strip().split('\n')
        cpu = sum(float(l.split()[0]) for l in lines if l.strip())
        mem = sum(float(l.split()[1]) for l in lines if l.strip()) / 1024.0
    except:
        cpu, mem = 0, 0

    # USB Stats
    try:
        disc = subprocess.check_output("dmesg | grep -Ei 'usb|rtl|airspy' | grep -Ei 'disconnect|reconnecting|resubmit' | wc -l", shell=True).decode().strip()
        pwr = subprocess.check_output("dmesg | grep -Ei 'over-current|power-off|vbus|babble' | wc -l", shell=True).decode().strip()
    except:
        disc, pwr = 0, 0
        
    return cpu, mem, disc, pwr

if len(sys.argv) > 1 and sys.argv[1] == 'config':
    # Graph 1: Resources
    print("multigraph sdr_resources")
    print("graph_title SDRTrunk CPU & Memory")
    print("graph_category radio")
    print("graph_vlabel % / MB")
    print("cpu.label CPU Usage (%)")
    print("mem.label RAM Usage (MB)")
    
    # Graph 2: USB Stability (Separate scale for small error counts)
    print("multigraph sdr_usb")
    print("graph_title SDR USB Stability")
    print("graph_category radio")
    print("graph_vlabel events")
    print("disc.label Disconnects")
    print("disc.type DERIVE")
    print("pwr.label Power Sags")
    print("pwr.type DERIVE")
    sys.exit(0)

cpu, mem, disc, pwr = get_stats()

print("multigraph sdr_resources")
print(f"cpu.value {cpu}")
print(f"mem.value {mem}")

print("multigraph sdr_usb")
print(f"disc.value {disc}")
print(f"pwr.value {pwr}")
