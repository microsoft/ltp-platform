# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM golang:1.25.5 AS build

ARG TARGETOS
ARG TARGETARCH

ARG GOOS=${TARGETOS}
ARG GOARCH=${TARGETARCH}

ARG VERSION="v0.18.0"
ARG GIT_COMMIT="3c9ffca94"

RUN git clone --branch ${VERSION} --single-branch https://github.com/NVIDIA/k8s-device-plugin.git /usr/src/k8s-nvidia-device-plugin

RUN mkdir /artifacts
WORKDIR /usr/src/k8s-nvidia-device-plugin

RUN make PREFIX=/artifacts cmds

FROM nvcr.io/nvidia/distroless/go:v3.2.2-dev AS application

USER 0:0
SHELL ["/busybox/sh", "-c"]
RUN ln -s /busybox/sh /bin/sh

ENV NVIDIA_DISABLE_REQUIRE="true"
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

ARG VERSION="v0.18.0"
ARG GIT_COMMIT="3c9ffca94"

LABEL io.k8s.display-name="NVIDIA Device Plugin"
LABEL name="NVIDIA Device Plugin"
LABEL vendor="NVIDIA"
LABEL version=${VERSION}
LABEL com.nvidia.git-commit=${GIT_COMMIT}
LABEL release="${VERSION}-homebrew"
LABEL summary="NVIDIA device plugin for Kubernetes"
LABEL description="See summary"


COPY --from=build /artifacts/config-manager         /usr/bin/config-manager
COPY --from=build /artifacts/gpu-feature-discovery  /usr/bin/gpu-feature-discovery
COPY --from=build /artifacts/mps-control-daemon     /usr/bin/mps-control-daemon
COPY --from=build /artifacts/nvidia-device-plugin   /usr/bin/nvidia-device-plugin

ENTRYPOINT ["nvidia-device-plugin"]