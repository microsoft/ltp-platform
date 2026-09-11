# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


FROM golang:1.26.6 AS azcopy-builder

ARG AZCOPY_VERSION=10.32.8

WORKDIR /src
RUN git clone --depth 1 --branch "v${AZCOPY_VERSION}" \
        https://github.com/Azure/azure-storage-azcopy.git . && \
    go get golang.org/x/crypto@v0.56.0 && \
    go mod tidy && \
    CGO_ENABLED=0 go build -tags netgo -o /azcopy

FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    curl \
    iproute2 \
    net-tools \
    openssh-client \
    openssh-server \
    parallel \
    pssh \
    rsync && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
COPY --from=azcopy-builder /azcopy /usr/local/bin/azcopy

ENV SSHD_PORT=23333 \
    RSYNC_PORT=8873
RUN echo SSHD_PORT="$SSHD_PORT" >> /etc/environment && \
    echo RSYNC_PORT="$RSYNC_PORT" >> /etc/environment
RUN mkdir -p /root/.ssh && \
    touch /root/.ssh/authorized_keys && \
    mkdir -p /var/run/sshd && \
    sed -i "s/[# ]*PermitRootLogin prohibit-password/PermitRootLogin yes/" /etc/ssh/sshd_config && \
    sed -i "s/[# ]*PermitUserEnvironment no/PermitUserEnvironment yes/" /etc/ssh/sshd_config && \
    sed -i "s/[# ]*Port.*/Port ${SSHD_PORT}/" /etc/ssh/sshd_config && \
    cat /etc/ssh/ssh_host_ed25519_key.pub >> /root/.ssh/authorized_keys && \
    sed -i "s/RSYNC_ENABLE=false/RSYNC_ENABLE=true/" /etc/default/rsync && \
    echo "* soft nofile 1048576\n* hard nofile 1048576" >> /etc/security/limits.conf && \
    echo "root soft nofile 1048576\nroot hard nofile 1048576" >> /etc/security/limits.conf

WORKDIR /usr/src/app
COPY ./src .

COPY ./bin/* /usr/local/cluster-local-storage/
RUN chmod -R 0755 /usr/local/cluster-local-storage/

RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt && pip3 install --no-cache-dir --upgrade "urllib3>=2.5.0"

ENTRYPOINT ["/bin/bash", "-c", "/usr/local/cluster-local-storage/init.sh && python3 service.py"]
