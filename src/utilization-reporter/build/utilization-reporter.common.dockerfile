FROM python:3.12

RUN apt update && apt upgrade -y && apt clean && rm -rf /var/lib/apt/lists/*

WORKDIR /utilization-reporter

RUN mkdir -p /utilization-reporter
COPY src/* /utilization-reporter/

RUN pip install -r requirements.txt
