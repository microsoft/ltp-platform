#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -x

# Step 1: Enable and Start NVIDIA Fabric Manager and DCGM Services
systemctl enable --now nvidia-fabricmanager.service

# Step 2: Configure and Enable NVIDIA Persistence Daemon
useradd -c "NVIDIA Persistence Daemon,,," -U -s /usr/sbin/nologin -d /nonexistent -M nvidia-persistenced
cat > /etc/systemd/system/nvidia-persistenced.service << EOL
[Unit]
Description=NVIDIA Persistence Daemon
After=syslog.target
Wants=nvidia-fabricmanager.service
StopWhenUnneeded=true

[Service]
Type=forking
Restart=always
ExecStart=/usr/bin/nvidia-persistenced --user nvidia-persistenced --persistence-mode --verbose
ExecStopPost=/bin/rm -rf /var/run/nvidia-persistenced/*
TimeoutSec=300

[Install]
WantedBy=multi-user.target
EOL


systemctl enable --now nvidia-persistenced.service
systemctl enable --now nvidia-dcgm.service

# Step 3: Add "nvidia_peermem" Module to Load at Boot
if ! grep -q "^nvidia_peermem" /etc/modules; then
    echo "nvidia_peermem" >> /etc/modules
fi

# Step 4: Configure GPU and Memory Clocks
MEM_CLOCK=$1
GPU_CLOCK=$2

cat > /etc/systemd/system/nvidia-clock-setup.service << EOL
[Unit]
Description=NVIDIA GPU Clock Setup
After=nvidia-persistenced.service
Wants=nvidia-persistenced.service

[Service]
Type=oneshot
ExecStart=/bin/bash -c "nvidia-smi -ac ${MEM_CLOCK},${GPU_CLOCK} && modprobe nvidia_peermem"

[Install]
WantedBy=multi-user.target
EOL

# Enable the clock setup service
systemctl enable --now nvidia-clock-setup.service
