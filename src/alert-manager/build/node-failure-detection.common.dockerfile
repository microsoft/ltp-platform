# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    vim \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# Create app directory
WORKDIR /app

# Copy requirements and install dependencies
COPY ./src/node-failure-detection/requirements.txt .
RUN pip3 install -r requirements.txt

# Copy the node-failure-detection source code
COPY ./src/node-failure-detection/ .

# The specific service (monitor or detector) will be specified via CMD in the deployment 