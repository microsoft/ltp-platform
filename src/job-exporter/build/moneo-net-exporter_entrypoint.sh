#!/bin/bash

INTERVAL="${1}"

# Starts Network Exporter with specified InfiniBand sysfs path
if lspci | grep -qi 'infiniband'; then
    python3 /Moneo/src/worker/exporters/net_exporter.py --inifiband_sysfs=/hostsys/class/infiniband --update_freq=$INTERVAL &
    echo "Network Exporter Started!"
else
    echo "/hostsys/class/infiniband not found, Network Exporter not started."
    sleep infinity
fi

# Waits for any process to exit and returns the exit status
wait -n
exit $?
