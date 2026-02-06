# Copyright (c) Microsoft Corporation
# All rights reserved.
#
# MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
# to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
# BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Build stage
FROM node:20 AS builder

RUN npm install -g npm@latest

WORKDIR /usr/src/app

# Copy all files first (needed for local dependencies)
COPY . .

RUN corepack enable && corepack install -g yarn@4.2.2

# Install all dependencies including devDependencies
RUN yarn install

# Manually remove devDependencies from node_modules
# This is more reliable than trying to reinstall
RUN yarn plugin import https://raw.githubusercontent.com/yarnpkg/berry/master/packages/plugin-production-install/bin/%40yarnpkg/plugin-production-install.js || true
RUN for dep in $(node -pe "Object.keys(require('./package.json').devDependencies || {}).join(' ')"); do \
      rm -rf node_modules/$dep; \
    done

# Production stage - use slim image
FROM node:20-slim

WORKDIR /usr/src/app

ENV NODE_ENV=production \
    SERVER_PORT=8080 \
    UV_THREADPOOL_SIZE=8

# Copy only production dependencies and application code
COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY --from=builder /usr/src/app .

# Remove npm and corepack to eliminate security warnings
# Clean up apt cache
RUN apt-get update && apt upgrade -y && \
    apt purge -y subversion && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /usr/local/lib/node_modules

EXPOSE ${SERVER_PORT}

# Use node directly instead of npm
CMD ["node", "index.js"]
