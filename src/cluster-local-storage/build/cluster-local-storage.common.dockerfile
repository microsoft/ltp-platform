# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


FROM python:3.12

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    iproute2 \
    net-tools \
    openssh-client \
    openssh-server \
    parallel \
    pssh \
    rsync
RUN curl -sL https://aka.ms/downloadazcopy-v10-linux | tar -xz --strip-components=1 -C /usr/local/bin

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

RUN apt purge -y subversion && apt autoremove -y

WORKDIR /usr/src/app
COPY ./src .
COPY --chmod=0755 ./bin/*.sh /usr/local/cluster-local-storage/

RUN pip3 install -r requirements.txt

ENTRYPOINT ["/bin/bash", "-c", "/usr/local/cluster-local-storage/init.sh && python3 service.py"]
