#!/bin/bash
set -xe

git clone https://github.com/abuccts/rocm-container-runtime
cd ./rocm-container-runtime

bash install.sh