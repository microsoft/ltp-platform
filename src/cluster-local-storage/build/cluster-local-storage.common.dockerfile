# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


FROM python:3.12-slim

ARG AZCOPY_VERSION=10.32.8
ARG AZCOPY_SHA256=a95277dbc265912cefdddbaf251aa99ec648cb18ba657e8788066357a9022dc3

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
RUN curl -fsSL \
        "https://github.com/Azure/azure-storage-azcopy/releases/download/v${AZCOPY_VERSION}/azcopy_linux_amd64_${AZCOPY_VERSION}.tar.gz" \
        -o /tmp/azcopy.tar.gz && \
    echo "${AZCOPY_SHA256}  /tmp/azcopy.tar.gz" | sha256sum -c - && \
    tar -xzf /tmp/azcopy.tar.gz --strip-components=1 -C /usr/local/bin && \
    rm /tmp/azcopy.tar.gz

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
