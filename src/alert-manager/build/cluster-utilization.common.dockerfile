# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM python:3.12-slim

RUN apt-get update && apt-get upgrade -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY ./src/cluster-utilization .

RUN pip3 install -r requirements.txt

ENTRYPOINT ["python3", "send_alert.py"]
