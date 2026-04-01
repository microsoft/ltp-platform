# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM python:3.12-slim

RUN apt-get update && apt-get upgrade -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

COPY ./src/abnormal_detector .

RUN pip3 install -r requirements.txt

ENTRYPOINT ["python3", "detect_abnormal.py"]
