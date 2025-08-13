#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


if [ -n "$CLUSTER_LOCAL_STORAGE_WORKER" ]; then
  CLUSTER_LOCAL_STORAGE_IPOIB_NUM=${CLUSTER_LOCAL_STORAGE_IPOIB_NUM:-8}
  CLUSTER_LOCAL_STORAGE_IPOIB_PREFIX=${CLUSTER_LOCAL_STORAGE_IPOIB_PREFIX:-ib}
  idx=$((36#$(hostname | rev | cut -c1-2 | rev)))
  for i in $(seq 0 $((CLUSTER_LOCAL_STORAGE_IPOIB_NUM - 1))); do
    ip="172.2$i.$(( idx / 251 )).$(( idx % 251 + 4 ))"
    iface="$CLUSTER_LOCAL_STORAGE_IPOIB_PREFIX$i"
    if ! ifconfig $iface >/dev/null 2>&1; then
      echo "Interface $iface does not exist"
      exit 255
    else
    ifconfig $iface $ip netmask 255.255.255.0 || exit $?
    echo $iface $ip SUCCEED
  done
fi

env | grep CLUSTER_LOCAL_STORAGE >> /etc/environment

# ssh
cat > /root/.ssh/config << EOL
Host *
    Port $SSHD_PORT
    IdentityFile /etc/ssh/ssh_host_ed25519_key
    StrictHostKeyChecking no
EOL
service ssh restart

# rsync
cat > /etc/rsyncd.conf << EOL
port = $RSYNC_PORT
use chroot = yes
max connections = 16384
pid file = /var/run/rsyncd.pid
lock file = /var/run/rsync.lock
log file = /var/log/rsync.log

[clstore]
    path = $CLUSTER_LOCAL_STORAGE_ROOT
    comment = cluster local storage
    uid = root
    gid = root
    read only = false
    list = yes
EOL
service rsync restart
