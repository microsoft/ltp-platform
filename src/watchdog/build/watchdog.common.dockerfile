# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM golang:1.24.2-alpine3.21 as builder

ENV PROJECT_DIR=/src
ENV INSTALL_DIR=/opt/watchdog

RUN apk update && apk add --no-cache bash && \
  mkdir -p ${PROJECT_DIR} ${INSTALL_DIR}
COPY src ${PROJECT_DIR}
RUN ${PROJECT_DIR}/build/watchdog/go-build.sh && \
  mv ${PROJECT_DIR}/dist/watchdog/* ${INSTALL_DIR}

FROM alpine:3.21

ENV INSTALL_DIR=/opt/watchdog

RUN apk update && apk add --no-cache bash
RUN apk upgrade --no-cache

COPY --from=builder ${INSTALL_DIR} ${INSTALL_DIR}
WORKDIR ${INSTALL_DIR}
