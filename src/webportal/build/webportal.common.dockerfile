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
FROM node:carbon-slim

WORKDIR /usr/src/app

ENV NODE_ENV=production \
    SERVER_PORT=8080

# Copy only production dependencies
COPY --from=builder /usr/src/app/node_modules_prod ./node_modules

# Copy built assets and necessary runtime files
COPY --from=builder /usr/src/app/dist ./dist
COPY --from=builder /usr/src/app/server ./server
COPY --from=builder /usr/src/app/config ./config
COPY --from=builder /usr/src/app/src/app/env.js.template ./src/app/env.js.template
COPY --from=builder /usr/src/app/package.json ./package.json
COPY --from=builder /usr/src/app/version ./version

# Create a simple env.js generator script using Node.js (no npm needed)
RUN echo 'const fs = require("fs"); \
const template = fs.readFileSync("src/app/env.js.template", "utf8"); \
const result = template.replace(/\$\{([^}]+)\}/g, (_, key) => process.env[key] || ""); \
fs.writeFileSync("dist/env.js", result);' > /generate-env.js

EXPOSE ${SERVER_PORT}

# Generate env.js at startup using Node.js, then start server
CMD node /generate-env.js && node server
