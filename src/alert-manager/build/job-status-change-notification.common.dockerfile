# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Build stage
FROM node:20 AS builder

RUN npm install -g npm@latest

WORKDIR /usr/src/app

# Copy all files first (needed for local file dependencies like openpaidbsdk)
COPY ./src/job-status-change-notification .

RUN corepack enable && corepack install -g yarn@4.2.2

# Install all dependencies including devDependencies
RUN yarn install

# Manually remove devDependencies from node_modules
RUN for dep in $(node -pe "Object.keys(require('./package.json').devDependencies || {}).join(' ')"); do \
      rm -rf node_modules/$dep; \
    done

# Production stage - use slim image
FROM node:20-slim

WORKDIR /usr/src/app

ENV NODE_ENV=production

# Copy only production dependencies and application code
COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY ./src/job-status-change-notification .

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
