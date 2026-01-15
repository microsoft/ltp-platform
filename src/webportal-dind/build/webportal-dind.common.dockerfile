FROM ubuntu:latest

RUN apt-get update && apt-get upgrade -y

RUN mkdir -p /var/lib/docker-vfs

COPY build/install.sh .

RUN chmod +x install.sh

RUN bash ./install.sh