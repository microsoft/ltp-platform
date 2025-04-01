#!/bin/bash

set -x

DEBIAN_FRONTEND=noninteractive apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y network-manager net-tools rsync || echo "Failed in apt install"


# rename
INIT=0
if [ ! -f /etc/udev/rules.d/70-persistent-ipoib.rules ]; then
  INIT=1
  for i in {0..7}; do
    old=$(basename $(ls -d /sys/class/net/ibP$((257+i))*))
    ip link set $old down
    ip link set $old name ib$i
    ip link set ib$i up
    echo "ACTION==\"add\", SUBSYSTEM==\"net\", DRIVERS==\"?*\", ATTR{type}==\"32\", ATTR{address}==\"?*$(cat /sys/class/net/ibP$((257+i))*/address | cut -d: -f13-)\", NAME=\"ib$i\"" | tee -a /etc/udev/rules.d/70-persistent-ipoib.rules
  done
fi


# nm
mkdir -p /etc/NetworkManager
cat > /etc/NetworkManager/NetworkManager.conf << 'EOL'
[main]
plugins=ifupdown,keyfile

[ifupdown]
managed=false

[keyfile]
unmanaged-devices=except:interface-name:ib*

[device]
wifi.scan-rand-mac-address=no
EOL
systemctl enable --now NetworkManager


# setup
cat > /usr/local/bin/setup_ipoib << 'EOL'
#!/bin/bash

for i in {0..7}; do
  if [ "$#" -eq 1 ]; then
    nmcli device set ib$i managed yes
    idx=$((36#$(hostname | rev | cut -c1-2 | rev)))
    nmcli con add type infiniband con-name ib$i ifname ib$i ipv4.method manual ipv4.addresses 172.2$i.$(( idx / 251 )).$(( idx % 251 + 4 ))/20
  fi
  nmcli con up ib$i
done
nmcli connection reload
EOL
chmod +x /usr/local/bin/setup_ipoib
if [ "$INIT" -eq 1 ]; then
  /usr/local/bin/setup_ipoib $INIT
fi

cat > /etc/systemd/system/setup-ipoib.service << EOL
[Unit]
Description=Setup IPoIB
After=network.target

[Service]
ExecStart=/usr/local/bin/setup_ipoib
Restart=no
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL
systemctl enable --now setup-ipoib


# rsync
cat > /etc/rsyncd.conf << EOL
use chroot = no
max connections = 1000
pid file = /var/run/rsyncd.pid
lock file = /var/run/rsync.lock
log file = /var/log/rsync.log

[paidata]
    path = /mntext
    comment = RAID
    uid = azureuser
    gid = azureuser
    read only = false
    list = yes
EOL
systemctl enable --now rsync
