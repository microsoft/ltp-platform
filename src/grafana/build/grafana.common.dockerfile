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


FROM ubuntu:22.04

ENV \
  GRAFANA_VERSION=10.4.4 \
  GF_PLUGIN_DIR=/grafana-plugins \
  GF_PATHS_LOGS=/var/log/grafana \
  GF_PATHS_DATA=/var/lib/grafana \
  UPGRADEALL=true


RUN \
  apt-get update && \
  apt-get -y --force-yes --no-install-recommends install libfontconfig wget ca-certificates adduser libfontconfig1 musl curl && \
  wget -O /tmp/grafana.deb https://dl.grafana.com/oss/release/grafana_${GRAFANA_VERSION}_amd64.deb && \
  dpkg -i /tmp/grafana.deb && \
  rm -f /tmp/grafana.deb && \
  ### branding && \
  apt-get autoremove -y --force-yes && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

COPY src/run-grafana.sh /usr/local/bin
COPY src/dashboards/* /usr/local/grafana/dashboards/

RUN sed -i 's/;*\s*allow_embedding\s*=\s*.*/allow_embedding = true/' /etc/grafana/grafana.ini
RUN sed -i 's/;*\s*root_url\s*=\s*.*/root_url = %(protocol)s:\/\/%(domain)s:%(http_port)s\/grafana\//' /etc/grafana/grafana.ini


ENTRYPOINT ["/usr/local/bin/run-grafana.sh"]
