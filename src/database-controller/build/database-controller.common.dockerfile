# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Build stage
FROM node:20 AS builder

RUN npm install -g npm@latest

WORKDIR /database-controller

COPY ./src ./src
COPY ./sdk ./sdk
COPY ./version ./version

WORKDIR src

# Install dependencies (Yarn 1 classic supports --production flag)
RUN yarn install --production --frozen-lockfile

# Modify package.json with version info (need json package)
RUN npm install json -g
RUN json -I -f package.json -e "this.paiVersion=\"`cat ../version/PAI.VERSION`\""
RUN json -I -f package.json -e "this.paiCommitVersion=\"`cat ../version/COMMIT.VERSION`\""

# Production stage - use slim image
FROM node:20-slim

WORKDIR /database-controller/src

# Copy only production dependencies and application code
COPY --from=builder /database-controller/src/node_modules ./node_modules
COPY --from=builder /database-controller/src/package.json ./package.json
COPY --from=builder /database-controller/src .
COPY --from=builder /database-controller/sdk ../sdk
COPY --from=builder /database-controller/version ../version

# Remove npm and corepack to eliminate security warnings
# Clean up apt cache
RUN apt-get update && apt upgrade -y && \
    apt purge -y subversion && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /usr/local/lib/node_modules

CMD ["sleep", "infinity"]
