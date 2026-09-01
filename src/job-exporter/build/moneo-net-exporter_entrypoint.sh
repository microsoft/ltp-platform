#!/bin/bash

INTERVAL="${1}"

# Starts Network Exporter when the mounted host sysfs contains an InfiniBand device.
if compgen -G '/hostsys/class/infiniband/*' > /dev/null; then
    python3 /Moneo/src/worker/exporters/net_exporter.py --inifiband_sysfs=/hostsys/class/infiniband --update_freq=$INTERVAL &
    echo "Network Exporter Started!"
else
    echo "No InfiniBand device found, Network Exporter not started."
    sleep infinity
fi

# Waits for any process to exit and returns the exit status
wait -n
exit $?
