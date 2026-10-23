#!/bin/bash

if lsmod | grep -qi amdgpu; then
    echo "AMD Graphics Card Detected."
    # Launches AMD RDC Daemon
    nohup /opt/rocm/bin/rdcd -u </dev/null >/dev/null 2>&1 &
    echo "rdc Daemon Started!"
    exec python3 /Moneo/src/worker/exporters/amd_exporter.py
elif lsmod | grep -qi nvidia; then
    echo "NVIDIA Graphics card detected."
    # Launches NVIDIA DCGM Daemon
    nohup nv-hostengine &
    echo "DCGM Daemon Started!"
    exec python3 /Moneo/src/worker/exporters/nvidia_exporter.py
else
    exec python3 /job_exporter/non_gpu_exporter.py --port "${1:-8000}"
fi
