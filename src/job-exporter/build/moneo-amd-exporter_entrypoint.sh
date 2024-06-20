#!/bin/bash

if lspci | grep -qi 'vga\|3d\|amd'; then
    echo "Graphics card detected."

    # Launches AMD RDC Daemon
    if [ -e /opt/rocm/bin/rdcd ]; then
        nohup /opt/rocm/bin/rdcd -u </dev/null >/dev/null 2>&1 &
        echo "rdc Daemon Started!"
    fi

    if [ -e /dev/kfd ] && [ -e /dev/dri ]; then
        python3 /Moneo/src/worker/exporters/amd_exporter.py &
        echo "AMD Exporter Started!"
    else
        echo "/dev/kdf and /dev/dri not found, AMD Exporter not started."
    fi
else
    echo "No graphics card detected."
fi

# Starts Network Exporter with specified InfiniBand sysfs path
if [ -e /hostsys/class/infiniband ]; then
    python3 /Moneo/src/worker/exporters/net_exporter.py --inifiband_sysfs=/hostsys/class/infiniband &
    echo "Network Exporter Started!"
else
    echo "/hostsys/class/infiniband not found, Network Exporter not started."
fi

# Starts Node Exporter
python3 /Moneo/src/worker/exporters/node_exporter.py &
echo "Node Exporter Started!"

# Waits for any process to exit and returns the exit status
wait -n
exit $?
