# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    postgresql-client \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy SDK (embedded in service)
COPY sdk /app/sdk
RUN pip install --no-cache-dir -e /app/sdk
RUN pip install pytest pytest-cov


# Copy service code
COPY src /app/src
# Alembic config now at service root
RUN mv /app/src/alembic.ini /app/
COPY src/alembic /app/alembic
COPY tests /app/tests


# Default command (can be overridden)
CMD ["python", "/app/src/schema_manager.py", "check"]


