#!/bin/bash
# This script is used to build the project

# Go to the parent directory of the root directory of the project
SCRIPT_PATH=$(cd $(dirname $0) && pwd -P)
cd $SCRIPT_PATH/../..

# Build the docker image
docker -t modelproxy:latest -f AIMiciusModelProxy/dockerfile/deploy.dockerfile . 