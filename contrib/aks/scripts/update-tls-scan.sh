#!/bin/bash

cat > /etc/systemd/system/update-tls-scan.service << EOL
[Unit]
Description=Update TLS Scan Config
After=network.target

[Service]
ExecStart=sed -i 's|<option name=\"TlsScanDisable\">0</option>|<option name=\"TlsScanDisable\">1</option>|' /etc/azsec/scans.d/vsatlsscan.xml
Restart=no
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL

systemctl enable --now update-tls-scan.service
