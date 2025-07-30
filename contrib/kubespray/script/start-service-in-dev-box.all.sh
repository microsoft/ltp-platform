#!/bin/bash
set -e
while getopts "c:n:" opt; do
  case $opt in
    c) config_folder="$OPTARG"
    ;;
    n) cluster_name="$OPTARG"
    ;;
    \?) echo "Invalid option -$OPTARG" >&2
    exit 1
    ;;
  esac
done

if  [ -z "$config_folder" ] || [ -z "$cluster_name" ]; then
  echo "Usage: $0 -c config_directory -n cluster_name "
  exit 1
fi

if [ ! -d "$config_folder" ]; then
  echo "Config folder not found: $config_folder"
  exit 1
fi
if [ ! -f "$config_folder/layout.yaml" ]; then
  echo "Layout file not found: $layout"
  exit 1
fi
if [ ! -f "$config_folder/config.yaml" ]; then
  echo "Config file not found: $config"
  exit 1
fi
if [ ! -f "$config_folder/services-configuration.yaml" ]; then
  echo "Services configuration file not found: $config"
  exit 1
fi

cluster_id_file=./cluster-id
# assume the workdir is pai
echo $cluster_name > $cluster_id_file

echo "Pushing cluster config to k8s..."
./paictl.py config push -p $config_folder -m service < $cluster_id_file

echo "Starting OpenPAI service..."
services=(
  cluster-configuration device-plugin node-exporter job-exporter openpai-runtime 
  log-manager prometheus grafana alert-manager watchdog internal-storage postgresql frameworkcontroller database-controller fluentd
  hivedscheduler rest-server webportal pylon
)

for service in "${services[@]}"; do
  echo ">> Starting $service..."
  ./paictl.py service start -n $service < $cluster_id_file
  if [ $? -ne 0 ]; then
    echo ">> Failed to start $service"
    exit 1
  fi
  echo ">> $service started successfully"
done

rm $cluster_id_file