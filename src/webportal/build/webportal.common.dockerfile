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

# Build stage - install all dependencies and build
FROM node:carbon AS builder

WORKDIR /usr/src/app

COPY dependency/ ../../
COPY . .

RUN rm -rf .env && yarn --no-git-tag-version --new-version version \
    "$(cat version/PAI.VERSION)"
RUN npm install json -g
RUN json -I -f package.json -e "this.commitVersion=\"`cat version/COMMIT.VERSION`\""

# Install all dependencies including devDependencies for building
RUN yarn install --production=false

# Build the frontend assets
RUN npm run build

# Now install only production dependencies in a separate location
RUN yarn install --production=true --modules-folder ./node_modules_prod

# Production stage - use slim image
FROM node:carbon

WORKDIR /usr/src/app

ENV NODE_ENV=production \
    SERVER_PORT=8080

# Copy only production dependencies
COPY --from=builder /usr/src/app/node_modules_prod ./node_modules

# Copy built assets and necessary files
COPY --from=builder /usr/src/app/dist ./dist
COPY --from=builder /usr/src/app/server ./server
COPY --from=builder /usr/src/app/package.json ./package.json
COPY --from=builder /usr/src/app/version ./version

# Clean up apt cache
RUN apt-get update && apt upgrade -y && \
    apt purge -y subversion && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

EXPOSE ${SERVER_PORT}

# Use node directly instead of npm
CMD ["node", "server"]
