#!/bin/bash

set -x

useradd -c "NVIDIA Persistence Daemon,,," -U -s /usr/sbin/nologin -d /nonexistent -M nvidia-persistenced
cat > /etc/systemd/system/nvidia-persistenced.service << EOL
[Unit]
Description=NVIDIA Persistence Daemon
Wants=syslog.target
After=nvidia-fabricmanager.service
StopWhenUnneeded=true
[Service]
Type=forking
ExecStart=/usr/bin/nvidia-persistenced --user nvidia-persistenced --persistence-mode --verbose
ExecStopPost=/bin/rm -rf /var/run/nvidia-persistenced
[Install]
WantedBy=multi-user.target
EOL

nvidia-smi -mig DISABLED
systemctl enable nvidia-persistenced.service
