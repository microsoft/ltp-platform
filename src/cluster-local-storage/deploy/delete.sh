#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.


pushd $(dirname "$0") > /dev/null

/bin/bash stop.sh || exit $?

popd > /dev/null
