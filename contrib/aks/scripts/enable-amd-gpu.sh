#!/bin/bash

cat > /etc/systemd/system/amdgpu.service << EOL
[Unit]
Description=Load AMD GPU kernel module
After=network.target

[Service]
Type=oneshot
ExecStart=/sbin/modprobe amdgpu

[Install]
WantedBy=multi-user.target
EOL

systemctl enable amdgpu.service
systemctl start amdgpu.service