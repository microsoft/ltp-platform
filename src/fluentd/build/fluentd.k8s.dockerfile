# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM fluent/fluentd:v1.17.1-debian-1.0

USER root

# workaround different system page sizes by disabling jemalloc
ENV LD_PRELOAD="" \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    ruby-dev \
    make \
    gcc \
    libc6-dev \
    libpq-dev \
    libpq5 \
    postgresql-client \
    git \
    ca-certificates

RUN gem install fluent-plugin-concat && \
    gem install fluent-plugin-parser-cri --no-document && \
    gem install bundler -v 2.3.27 && \
    gem install rake && \
    gem install pg -v 1.5.9 && \
    gem install bigdecimal --no-document

# Build fluent-plugin-pgjson from scratch
# Original fluent-plugin-pgjson is from https://github.com/fluent-plugins-nursery/fluent-plugin-pgjson
# Original plugin cannot retry connecting when database connection is lost,
# and is not thread-safe. These two problems are fixed by modifying codes.
COPY src/fluent-plugin-pgjson /fluent-plugin-pgjson
RUN cd /fluent-plugin-pgjson && \
    git init && \
    git add . && \
    rake build && \
    gem install --local ./pkg/fluent-plugin-pgjson-1.0.0.gem && \
    rm -rf /fluent-plugin-pgjson

# cleanup
RUN gem sources --clear-all && \
    rm -rf /tmp/* /var/tmp/* /usr/lib/ruby/gems/*/cache/*.gem && \
    apt-get purge -y --auto-remove build-essential make gcc libc6-dev libpq-dev && \
    apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY build/fluent.conf /fluentd/etc/
