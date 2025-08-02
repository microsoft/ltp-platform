#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


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

[data]
    path = /data
    comment = RAID
    uid = nobody
    gid = nogroup
    read only = false
    list = yes
EOL
service rsync restart
