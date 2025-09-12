FROM mcr.microsoft.com/cbl-mariner/base/python:3

WORKDIR /utilization-reporter

RUN mkdir -p /utilization-reporter
COPY src/* /utilization-reporter/

RUN pip install -r requirements.txt
