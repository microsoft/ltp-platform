# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM mcr.microsoft.com/azurelinux/base/python:3.12

WORKDIR /app

RUN tdnf update -y && tdnf clean all

# install kusto sdk
COPY ./src/node-issue-classifier .

RUN tdnf remove -y python3-pip && \
    python3 -m ensurepip && \
    python3 -m pip install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Run the service
ENTRYPOINT ["python3", "classifier_scheduler.py"]