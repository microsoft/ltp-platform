FROM python:3.12-slim

RUN apt-get update && apt-get upgrade -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

WORKDIR /utilization-reporter

RUN mkdir -p /utilization-reporter
COPY src/* /utilization-reporter/

RUN pip install -r requirements.txt
