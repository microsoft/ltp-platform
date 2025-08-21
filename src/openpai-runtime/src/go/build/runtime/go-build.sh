#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

set -o errexit
set -o nounset
set -o pipefail

BASH_DIR=$(cd $(dirname ${BASH_SOURCE}) && pwd)
# Ensure ${PROJECT_DIR} is ${GOPATH}/src/github.com/microsoft/hivedscheduler
PROJECT_DIR=${BASH_DIR}/../..
DIST_DIR=${PROJECT_DIR}/dist/runtime

cd ${PROJECT_DIR}

rm -rf ${DIST_DIR}
mkdir -p ${DIST_DIR}

CGO_ENABLED=0 go build -o ${DIST_DIR}/exithandler cmd/exithandler/*
CGO_ENABLED=0 go build -o ${DIST_DIR}/barrier cmd/barrier/*
chmod a+x ${DIST_DIR}/exithandler
chmod a+x ${DIST_DIR}/barrier

echo Succeeded to build binary distribution into ${DIST_DIR}:
cd ${DIST_DIR} && ls -lR .
