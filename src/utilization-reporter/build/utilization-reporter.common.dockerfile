FROM python:3.12

RUN apt update && apt upgrade -y

RUN apt purge -y subversion && apt autoremove -y

RUN pip install --upgrade pip

WORKDIR /utilization-reporter

RUN mkdir -p /utilization-reporter
COPY src/* /utilization-reporter/

RUN pip install -r requirements.txt
