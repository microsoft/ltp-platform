#!/bin/bash

set -x

cat > /usr/local/bin/raid-setup.sh << EOL
#!/bin/bash
set -x

mkdir -p /mntext

# Try to assemble existing RAID
if [[ ! -b /dev/md0 ]]; then
    echo "Attempting to assemble RAID..."
    mdadm --assemble --scan
fi

# Check if RAID is already mounted
if mount | grep /dev/md0
then
    echo "RAID already mounted. Skipping RAID recreation."
else
    # Check if RAID exists and has a UUID
    uuid=\$(lsblk /dev/md0 --output UUID --noheadings | xargs)
    if [[ -n \$uuid ]]; then
        if grep \$uuid /etc/fstab
        then
            echo "UUID found in fstab. Mounting..."
            mount /mntext
            exit 0
        else
            echo "RAID UUID mismatch in fstab. Restoring backup and rebooting..."
            [[ -f /etc/fstab.bak ]] && mv /etc/fstab.bak /etc/fstab
            sleep 2
            reboot
        fi
    fi

    # If RAID exists but is not properly set up, stop and remove it
    if [[ -b /dev/md0 ]]
    then
        mdadm --stop /dev/md0
        mdadm --remove /dev/md0
    fi

    # Get NVMe disks
    nvme_list=\$(lsblk -pl|grep nvme | grep -v part|awk '{print \$1}')
    nvme_count=\$(echo \$nvme_list |wc -w)

    # Create RAID 0
    mdadm --create --run /dev/md0 --level=0 --raid-device=\$nvme_count \$nvme_list
    mdadm --detail /dev/md0
    # Format and get UUID
    mkfs -t ext4 -F /dev/md0
    sleep 5
    lsblk -f

    # Retry UUID fetch
    for ((i=0; i<10; i++)); do
    uuid=\$(lsblk /dev/md0 --output UUID --noheadings)
    if [ -n "\$uuid" ]; then
        break
    else
        echo "UUID not found. Attempt \$((i + 1))/10. Retrying..."
        sleep 5
    fi
    done

    # Save RAID info to assemble on boot
    mdadm --detail --scan >> /etc/mdadm/mdadm.conf

    # Update fstab
    output="UUID=\$uuid /mntext ext4 errors=remount-ro 0 1"
    if [[ -f /etc/fstab.bak ]]
    then
    cp /etc/fstab.bak /etc/fstab
    else
    cp /etc/fstab /etc/fstab.bak
    fi
    echo \$output | tee --append /etc/fstab
    systemctl daemon-reload

    for ((i=0; i<5; i++))
    do
    mount /mntext
        if mount|grep md0
        then
            break
        else
            sleep 2
        fi
    done
fi

# Bind mount kubelet and containerd paths
mkdir -p /mntext/kubelet
mkdir -p /var/lib/kubelet
output="/mntext/kubelet /var/lib/kubelet ext4 defaults,bind,systemd.requires-mounts-for=/mntext 0 1"
echo \$output | tee --append /etc/fstab
systemctl daemon-reload
mount /var/lib/kubelet

mkdir -p /mntext/containerd
mkdir -p /var/lib/containerd
output="/mntext/containerd /var/lib/containerd ext4 defaults,bind,systemd.requires-mounts-for=/mntext 0 1"
echo \$output |  tee --append /etc/fstab
systemctl daemon-reload
mount /var/lib/containerd
sleep 5

EOL

chmod +x /usr/local/bin/raid-setup.sh

tee /etc/systemd/system/raid-setup.service << EOF
[Unit]
Description=raid setup
DefaultDependencies=no
Before=local-fs-pre.target blk-availability.service
BindsTo=multipathd.service
After=multipathd.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/raid-setup.sh
RemainAfterExit=yes
TimeoutSec=300

[Install]
WantedBy=local-fs-pre.target
EOF

systemctl enable raid-setup.service
