# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM golang:1.24.3-alpine3.21 AS builder

ARG TEST=false
ENV GOPATH=/go
ENV PROJECT_DIR=/src
ENV INSTALL_DIR=/opt/hivedscheduler/hivedscheduler

RUN apk update && apk add --no-cache bash
RUN mkdir -p ${PROJECT_DIR} ${INSTALL_DIR}
COPY src ${PROJECT_DIR}
RUN if [ ${TEST} == "true" ]; \
  then ${PROJECT_DIR}/build/hivedscheduler/go-build.sh test; \
  else ${PROJECT_DIR}/build/hivedscheduler/go-build.sh; fi && \
  mv ${PROJECT_DIR}/dist/hivedscheduler/* ${INSTALL_DIR}


FROM alpine:3.21

ENV INSTALL_DIR=/opt/hivedscheduler/hivedscheduler

RUN apk update && apk add --no-cache bash
RUN apk upgrade --no-cache

COPY --from=builder ${INSTALL_DIR} ${INSTALL_DIR}
WORKDIR ${INSTALL_DIR}

ENTRYPOINT ["./start.sh"]
