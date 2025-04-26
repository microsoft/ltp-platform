# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM python:3.12

RUN apt update && apt upgrade -y
RUN pip install --upgrade pip

COPY ./src/abnormal_detector .

RUN pip3 install -r requirements.txt

ENTRYPOINT ["python3", "detect_abnormal.py"]
