# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM mcr.microsoft.com/azurelinux/base/python:3.12

WORKDIR /usr/src/app

RUN tdnf update -y && tdnf clean all

COPY ./src/node-recycler .

RUN pip3 install -r requirements.txt

ENTRYPOINT ["python3", "recycler.py"]
