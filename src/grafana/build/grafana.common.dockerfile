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
FROM node:24 AS infinity-build

ARG TARGETOS
ARG TARGETARCH

ENV GOVERSION=1.26.10
ENV GRAFANA_INFINITY_PLUGIN_VERSION=v3.11.3

ENV GOPATH=/usr/local/go
ENV GOBIN=$GOPATH/bin
ENV PATH=$GOBIN:$PATH

RUN wget https://go.dev/dl/go${GOVERSION}.linux-${TARGETARCH}.tar.gz && \
    tar -C /usr/local -xzf go${GOVERSION}.linux-${TARGETARCH}.tar.gz

WORKDIR /usr/src/plugin

RUN git clone --branch ${GRAFANA_INFINITY_PLUGIN_VERSION} --depth 1 https://github.com/grafana/grafana-infinity-datasource.git /usr/src/plugin

RUN go get golang.org/x/crypto@v0.56.0 && \
    go get google.golang.org/grpc@v1.83.2 && \
    go get golang.org/x/net@v0.62.0 && \
    go mod tidy

RUN go install github.com/magefile/mage@latest

RUN corepack enable && yarn && yarn build

RUN if [ "$TARGETARCH" = "amd64" ]; then \
  mage build:linux; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
  mage build:linuxARM64; \
    else \
  echo "Unsupported architecture: $TARGETARCH" && exit 1; \
    fi

FROM node:24 AS prometheus-build

ARG TARGETARCH
ARG GRAFANA_PROMETHEUS_PLUGIN_VERSION=13.2.5
ARG GRAFANA_PROMETHEUS_GO_VERSION=1.27.3

ENV GOPATH=/go
ENV GOBIN=$GOPATH/bin
ENV PATH=/usr/local/go/bin:$GOBIN:$PATH

RUN case "${TARGETARCH}" in \
      amd64|arm64) ;; \
      *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac && \
    wget https://go.dev/dl/go${GRAFANA_PROMETHEUS_GO_VERSION}.linux-${TARGETARCH}.tar.gz && \
    tar -C /usr/local -xzf go${GRAFANA_PROMETHEUS_GO_VERSION}.linux-${TARGETARCH}.tar.gz

WORKDIR /usr/src/prometheus

RUN git clone --branch v${GRAFANA_PROMETHEUS_PLUGIN_VERSION} --depth 1 \
    https://github.com/grafana/grafana-prometheus-datasource.git .

RUN go -C pkg/promlib get golang.org/x/net@v0.62.0 && \
    go -C pkg/promlib mod tidy && \
    go get golang.org/x/net@v0.62.0 && \
    go mod tidy

RUN corepack enable npm && npm ci --no-audit --no-fund && npm run build

# Expose a single Linux target through the upstream SDK.
RUN go install github.com/magefile/mage@v1.17.2 && \
    printf '\nfunc BuildLinux() error { return build.Build{}.Custom("linux", "%s") }\n' \
      "${TARGETARCH}" >> Magefile.go && \
    mage buildLinux && \
    test ! -e dist/MANIFEST.txt

FROM ubuntu:22.04

ARG TARGETARCH
ARG GRAFANA_BUILD_ID=40412481033
ENV \
  GRAFANA_VERSION=13.3.0 \
  GF_PLUGIN_DIR=/grafana-plugins \
  GF_PATHS_LOGS=/var/log/grafana \
  GF_PATHS_DATA=/var/lib/grafana \
  GF_PLUGINS_PREINSTALL_DISABLED=true \
  GF_PLUGINS_DISABLE_PLUGINS=cloudwatch,elasticsearch,grafana-postgresql-datasource,grafana-pyroscope-datasource,influxdb,jaeger,loki,mssql,mysql,opentsdb,stackdriver,tempo,zipkin \
  UPGRADEALL=false


RUN \
  apt-get update && \
  apt-get -y --force-yes --no-install-recommends install libfontconfig wget ca-certificates adduser libfontconfig1 musl curl jq && \
  wget -O /tmp/grafana.deb https://dl.grafana.com/grafana/release/${GRAFANA_VERSION}/grafana_${GRAFANA_VERSION}_${GRAFANA_BUILD_ID}_linux_${TARGETARCH}.deb && \
  apt-get -y --no-install-recommends install /tmp/grafana.deb && \
  rm -f /tmp/grafana.deb && \
  ### branding && \
  apt-get autoremove -y --force-yes && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get upgrade -y

# Remove unused plugins and replace bundled Prometheus with the patched source build.
RUN rm -rf \
      /usr/share/grafana/data/plugins-bundled/cloudwatch \
      /usr/share/grafana/data/plugins-bundled/elasticsearch \
      /usr/share/grafana/data/plugins-bundled/grafana-postgresql-datasource \
      /usr/share/grafana/data/plugins-bundled/grafana-pyroscope-datasource \
      /usr/share/grafana/data/plugins-bundled/influxdb \
      /usr/share/grafana/data/plugins-bundled/jaeger \
      /usr/share/grafana/data/plugins-bundled/loki \
      /usr/share/grafana/data/plugins-bundled/mssql \
      /usr/share/grafana/data/plugins-bundled/mysql \
      /usr/share/grafana/data/plugins-bundled/opentsdb \
      /usr/share/grafana/data/plugins-bundled/prometheus \
      /usr/share/grafana/data/plugins-bundled/stackdriver \
      /usr/share/grafana/data/plugins-bundled/tempo \
      /usr/share/grafana/data/plugins-bundled/zipkin \
      /var/lib/grafana/plugins-bundled/cloudwatch \
      /var/lib/grafana/plugins-bundled/elasticsearch \
      /var/lib/grafana/plugins-bundled/grafana-postgresql-datasource \
      /var/lib/grafana/plugins-bundled/grafana-pyroscope-datasource \
      /var/lib/grafana/plugins-bundled/influxdb \
      /var/lib/grafana/plugins-bundled/jaeger \
      /var/lib/grafana/plugins-bundled/loki \
      /var/lib/grafana/plugins-bundled/mssql \
      /var/lib/grafana/plugins-bundled/mysql \
      /var/lib/grafana/plugins-bundled/opentsdb \
      /var/lib/grafana/plugins-bundled/prometheus \
      /var/lib/grafana/plugins-bundled/stackdriver \
      /var/lib/grafana/plugins-bundled/tempo \
      /var/lib/grafana/plugins-bundled/zipkin

COPY --from=infinity-build /usr/src/plugin/dist ${GF_PLUGIN_DIR}/yesoreyeram-infinity-datasource
COPY --from=prometheus-build /usr/src/prometheus/dist ${GF_PLUGIN_DIR}/prometheus

COPY src/run-grafana.sh /usr/local/bin

RUN sed -i 's/;*\s*allow_embedding\s*=\s*.*/allow_embedding = true/' /etc/grafana/grafana.ini
RUN sed -i 's/;*\s*root_url\s*=\s*.*/root_url = %(protocol)s:\/\/%(domain)s:%(http_port)s\/grafana\//' /etc/grafana/grafana.ini


ENTRYPOINT ["/usr/local/bin/run-grafana.sh"]
