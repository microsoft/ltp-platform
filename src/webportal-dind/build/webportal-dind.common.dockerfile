FROM ubuntu:latest

RUN apt-get update && apt-get upgrade -y

COPY build/install.sh .

RUN chmod +x install.sh

RUN bash ./install.sh