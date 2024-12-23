#!/bin/bash

cat > /etc/systemd/system/blobfuse-proxy.timer << EOL
[Unit]
Description=Timer to start blobfuse-proxy service after reboot

[Timer]
OnBootSec=10min
Unit=blobfuse-proxy.service

[Install]
WantedBy=timers.target
EOL

systemctl enable blobfuse-proxy.timer 
systemctl start blobfuse-proxy.timer
