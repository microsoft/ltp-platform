# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Build stage
FROM node:20 AS builder

RUN npm install -g npm@latest

WORKDIR /usr/src/app

COPY ./src/alert-handler/package.json ./src/alert-handler/yarn.lock* ./

RUN corepack enable && corepack install -g yarn@4.2.2
RUN yarn install --immutable

COPY ./src/alert-handler .

# Production stage - use slim image
FROM node:20-slim

WORKDIR /usr/src/app

ENV NODE_ENV=production

# Copy only production dependencies and application code
COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY ./src/alert-handler .

# Install python and dependencies
RUN apt-get update &&  apt upgrade -y && \
    apt purge -y subversion && \
    apt-get install -y python3-pip && \
    pip3 install --no-cache-dir -r requirements.txt --break-system-packages && \
    apt-get remove -y python3-pip && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Use node directly instead of npm
ENTRYPOINT ["node", "index.js"]
