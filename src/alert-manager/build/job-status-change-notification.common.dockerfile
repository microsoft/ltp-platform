# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Build stage
FROM node:24 AS builder

RUN npm install -g npm@latest

WORKDIR /usr/src/app

# Copy package files and openpaidbsdk source (needed for file: dependency resolution)
COPY ./src/job-status-change-notification/package.json ./src/job-status-change-notification/yarn.lock* ./src/job-status-change-notification/.yarnrc.yml ./
COPY ./src/job-status-change-notification/openpaidbsdk ./openpaidbsdk

RUN corepack enable && corepack install -g yarn@4.2.2
RUN yarn install
RUN for dep in $(node -pe "Object.keys(require('./package.json').devDependencies || {}).join(' ')"); do \
      rm -rf node_modules/$dep; \
    done

# Copy application source
COPY ./src/job-status-change-notification .

# Remove openpaidbsdk/node_modules if brought in by source COPY
RUN rm -rf openpaidbsdk/node_modules

# Production stage - use slim image
FROM node:24-slim

WORKDIR /usr/src/app

ENV NODE_ENV=production

# Copy everything from builder (clean, no devDependencies)
COPY --from=builder /usr/src/app .

# Remove npm and corepack to eliminate security warnings
# Clean up apt cache
RUN apt-get update && apt upgrade -y && \
    apt purge -y subversion && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /usr/local/lib/node_modules

# Use node directly instead of npm
ENTRYPOINT ["node", "index.js"]
