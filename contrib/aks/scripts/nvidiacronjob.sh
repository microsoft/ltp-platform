#!/bin/bash

MEM_CLOCK=$1
GPU_CLOCK=$2

echo "nvidia_peermem" >> /etc/modules

CRON_JOB="@reboot root { date; sleep 10; nvidia-smi -mig DISABLED; nvidia-smi -ac ${MEM_CLOCK},${GPU_CLOCK}; service nvidia-fabricmanager restart; modprobe nvidia_peermem; } >> /var/log/nvidia-cron.log 2>&1"
echo "$CRON_JOB" | sudo tee -a /etc/crontab
