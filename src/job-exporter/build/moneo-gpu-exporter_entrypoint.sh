#!/bin/bash

if lspci | grep -qi 'vga\|3d\|amd'; then
    echo "Graphics card detected."

    # Launches AMD RDC Daemon
    if [ -e /opt/rocm/bin/rdcd ]; then
        nohup /opt/rocm/bin/rdcd -u </dev/null >/dev/null 2>&1 &
        echo "rdc Daemon Started!"
        if [ -e /dev/kfd ] && [ -e /dev/dri ]; then
            python3 /Moneo/src/worker/exporters/amd_exporter.py &
            echo "AMD Exporter Started!"
        else
            echo "/dev/kdf and /dev/dri not found, AMD Exporter not started."
        fi
    fi
else
    echo "No graphics card detected."
    sleep infinity
fi

# Waits for any process to exit and returns the exit status
wait -n
exit $?
