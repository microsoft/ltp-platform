#!/bin/bash

# Copyright (c) Microsoft Corporation
# All rights reserved.
#
# MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
# to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
# BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

pushd $(dirname "$0") > /dev/null

echo "Preparing build dependencies for webportal-new..."

# Create dependency directory and copy docs and examples
mkdir -p "../dependency"
echo "Copying docs and examples..."
cp -arf "../../../docs" "../../../examples" "../dependency" 2>/dev/null || echo "Warning: docs or examples not found, skipping"

# Copy version files
echo "Copying version files..."
cp -arfT "../../../version" "../version" 2>/dev/null || {
    echo "Warning: version directory not found, creating default version"
    mkdir -p "../version"
    echo "1.0.0" > ../version/PAI.VERSION
}

# Set commit version
if [ "$ATTACH_COMMIT_ID" = true ]; then
    if command -v git &> /dev/null && git rev-parse --git-dir > /dev/null 2>&1; then
        echo "Setting commit version from git..."
        git rev-parse HEAD | cut -c1-6 > ../version/COMMIT.VERSION
    else
        echo "Git not available, using default commit version"
        echo "dev" > ../version/COMMIT.VERSION
    fi
else
    echo "" > ../version/COMMIT.VERSION
fi

echo "Build preparation complete!"
echo "  - dependency/ directory created"
echo "  - version/ files ready"
echo "  - PAI.VERSION: $(cat ../version/PAI.VERSION)"
echo "  - COMMIT.VERSION: $(cat ../version/COMMIT.VERSION)"

popd > /dev/null
