FROM ubuntu:latest

RUN apt-get update && apt-get upgrade -y

RUN apt-get install -y jq

RUN mkdir -p /var/lib/docker-vfs

COPY build/install.sh .

RUN chmod +x install.sh

RUN bash ./install.sh