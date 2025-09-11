#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

set -e

while getopts "l:c:" opt; do
  case $opt in
    l)
      LAYOUT=$OPTARG
      ;;
    c)
      CLUSTER_CONFIG=$OPTARG
      ;;
    \?)
      echo "Invalid option: -$OPTARG"
      exit 1
      ;;
  esac
done

echo "layout file path: ${LAYOUT}"
echo "cluster config file path: ${CLUSTER_CONFIG}"

function cleanup(){
  rm -rf ${HOME}/pai-post-installation/
}

trap cleanup EXIT

mkdir -p ${HOME}/pai-post-installation/
python3 script/machine_list_generator.py -l ${LAYOUT} -c ${CLUSTER_CONFIG} -o ${HOME}/pai-post-installation

ansible-playbook -i ${HOME}/pai-post-installation/machines.yml container-runtime-install.yml -e "@${CLUSTER_CONFIG}"
