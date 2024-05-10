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

FROM python:3.10

RUN apt-get update && apt-get install --no-install-recommends -y build-essential git && \
    git clone https://github.com/yadutaf/infilter --depth 1 && \
    cd infilter && make

FROM python:3.10

ENV CRI_VERSION=v1.28.0
RUN wget https://github.com/kubernetes-sigs/cri-tools/releases/download/$CRI_VERSION/crictl-$CRI_VERSION-linux-amd64.tar.gz && \
    tar zxvf crictl-$CRI_VERSION-linux-amd64.tar.gz -C /usr/local/bin && \
    rm crictl-$CRI_VERSION-linux-amd64.tar.gz && \
    apt-get update && apt-get install --no-install-recommends -y iftop lsof && \
    mkdir -p /job_exporter

RUN curl -sL http://repo.radeon.com/rocm/rocm.gpg.key | gpg --dearmor -o /usr/share/keyrings/rocm-archive-keyring.gpg && \
    sh -c 'echo deb [arch=amd64 signed-by=/usr/share/keyrings/rocm-archive-keyring.gpg] http://repo.radeon.com/rocm/apt/debian jammy main > /etc/apt/sources.list.d/rocm.list' && \
    apt-get update && apt-get install --no-install-recommends -y rocm-smi && \
    mkdir -p /opt/rocm && \
    cp -R $(dpkg -L rocm-smi | grep bin$) /opt/rocm && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /job_exporter/
COPY build/crictl.yaml /etc/crictl.yaml
RUN pip3 install -r /job_exporter/requirements.txt

COPY --from=0 infilter/infilter /usr/bin
COPY src/*.py /job_exporter/

ENV PATH "${PATH}:/opt/rocm/bin"
