#!/bin/bash

if lsmod | grep -qi amdgpu; then
    echo "AMD Graphics Card Detected."
    # Launches AMD RDC Daemon
    nohup /opt/rocm/bin/rdcd -u </dev/null >/dev/null 2>&1 &
    echo "rdc Daemon Started!"
    python3 /Moneo/src/worker/exporters/amd_exporter.py &
    echo "AMD Exporter Started!"
elif lsmod | grep -qi nvidia; then
    echo "NVIDIA Graphics card detected."
    python3 /update-dcgm.py
    # Launches NVIDIA DCGM Daemon
    nohup nv-hostengine &
    echo "DCGM Daemon Started!"
    python3 /Moneo/src/worker/exporters/nvidia_exporter.py &
    echo "NVIDIA Exporter Started!"
else
    echo "No Graphics Card Detected."
    sleep infinity
fi

# Waits for any process to exit and returns the exit status
wait
exit $?
