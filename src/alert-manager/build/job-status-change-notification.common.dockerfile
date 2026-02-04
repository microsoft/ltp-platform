# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Build stage
FROM node:20 AS builder

RUN npm install -g npm@latest

WORKDIR /usr/src/app

COPY ./src/job-status-change-notification/package.json ./src/job-status-change-notification/yarn.lock* ./src/job-status-change-notification/.yarnrc.yml ./

RUN corepack enable && corepack install -g yarn@4.2.2
RUN yarn workspaces focus --production

COPY ./src/job-status-change-notification .

# Production stage - use slim image
FROM node:20-slim

WORKDIR /usr/src/app

ENV NODE_ENV=production

# Copy only production dependencies and application code
COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY ./src/job-status-change-notification .

# Clean up apt cache
RUN apt-get update && apt upgrade -y && \
    apt purge -y subversion && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Use node directly instead of npm
ENTRYPOINT ["node", "index.js"]
