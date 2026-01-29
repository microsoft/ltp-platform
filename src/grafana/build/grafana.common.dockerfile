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
FROM node:20 AS build

ARG TARGETOS
ARG TARGETARCH

ENV GOVERSION=1.25.5
ENV PLUGINVERSION=v3.7.0

ENV GOPATH=/usr/local/go
ENV GOBIN=$GOPATH/bin
ENV PATH=$GOBIN:$PATH

RUN wget https://go.dev/dl/go${GOVERSION}.linux-${TARGETARCH}.tar.gz && \
    tar -C /usr/local -xzf go${GOVERSION}.linux-${TARGETARCH}.tar.gz

WORKDIR /usr/src/plugin

RUN git clone --branch ${PLUGINVERSION} --depth 1 https://github.com/grafana/grafana-infinity-datasource.git /usr/src/plugin

RUN go install github.com/magefile/mage@latest

RUN yarn && yarn build

RUN if [ "$TARGETARCH" = "amd64" ]; then \
  mage build:linux; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
  mage build:linuxARM64; \
    else \
  echo "Unsupported architecture: $TARGETARCH" && exit 1; \
    fi

FROM ubuntu:22.04

ARG TARGETARCH
ENV \
  GRAFANA_VERSION=10.4.18+security~01 \
  GF_PLUGIN_DIR=/grafana-plugins \
  GF_PATHS_LOGS=/var/log/grafana \
  GF_PATHS_DATA=/var/lib/grafana \
  UPGRADEALL=true


RUN \
  apt-get update && \
  apt-get -y --force-yes --no-install-recommends install libfontconfig wget ca-certificates adduser libfontconfig1 musl curl jq && \
  wget -O /tmp/grafana.deb https://dl.grafana.com/oss/release/grafana_${GRAFANA_VERSION}_${TARGETARCH}.deb && \
  dpkg -i /tmp/grafana.deb && \
  rm -f /tmp/grafana.deb && \
  ### branding && \
  apt-get autoremove -y --force-yes && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get upgrade -y

COPY --from=build /usr/src/plugin/dist ${GF_PLUGIN_DIR}/yesoreyeram-infinity-datasource

COPY src/run-grafana.sh /usr/local/bin

RUN sed -i 's/;*\s*allow_embedding\s*=\s*.*/allow_embedding = true/' /etc/grafana/grafana.ini
RUN sed -i 's/;*\s*root_url\s*=\s*.*/root_url = %(protocol)s:\/\/%(domain)s:%(http_port)s\/grafana\//' /etc/grafana/grafana.ini


ENTRYPOINT ["/usr/local/bin/run-grafana.sh"]
