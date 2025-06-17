# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM mcr.microsoft.com/azurelinux/base/python:3.12

WORKDIR /app

# install kusto sdk
COPY ./src/node-issue-classifier .

RUN pip3 install --no-cache-dir -r requirements.txt

# Run the service
ENTRYPOINT ["python3", "classifier_scheduler.py"]