# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM python:3.10-slim

RUN apt-get update && apt-get upgrade -y && apt-get clean

WORKDIR /app

# install kusto sdk
COPY ../../ltp-kusto-sdk /app/ltp-kusto-sdk
RUN pip3 install /app/ltp-kusto-sdk

# Copy requirements first to leverage Docker cache
COPY ./src/node-issue-classifier/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy source code
COPY ./src/node-issue-classifier /app/

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Run the service
ENTRYPOINT ["python3", "classifier_scheduler.py"]