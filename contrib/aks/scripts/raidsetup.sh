#!/bin/bash

set -x

cat > /usr/local/bin/raid-setup.sh << EOL
#!/bin/bash
set -x
uuid=\`lsblk /dev/md0 --output UUID --noheadings\`
if [[ -n \$uuid ]]
then
    if grep \$uuid /etc/fstab
    then
        exit 0
    else
        mv /etc/fstab.bak /etc/fstab
        echo "reboot since UUID in fstab changed"
        sleep 2
        reboot
    fi
fi

if [[ -b /dev/md0 ]]
then
    mdadm --stop /dev/md0
    mdadm --remove /dev/md0
fi

mkdir -p /mntext

nvme_list=\$(lsblk -pl|grep nvme | grep -v part|awk '{print \$1}')
nvme_count=\$(echo \$nvme_list |wc -w)
mdadm --create --run /dev/md0 --level=0 --raid-device=\$nvme_count \$nvme_list
mdadm --detail /dev/md0
mkfs -t ext4 -F /dev/md0
sleep 5
lsblk -f
uuid=\`lsblk /dev/md0 --output UUID --noheadings\`

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
TimeoutSec=100
ExecStartPre=/usr/local/bin/raid-setup.sh
ExecStart=/usr/bin/sleep infinity

[Install]
WantedBy=local-fs-pre.target
EOF

systemctl enable raid-setup.service
