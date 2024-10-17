# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM python:3.10

COPY ./src/abnormal_detector .

RUN pip3 install -r requirements.txt

ENTRYPOINT ["python3", "detect_abnormal.py"]
