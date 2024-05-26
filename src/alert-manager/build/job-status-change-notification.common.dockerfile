# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM node:20

WORKDIR /usr/src/app

ENV NODE_ENV=production

COPY ./src/job-status-change-notification .

RUN yarn install

ENTRYPOINT ["npm", "start"]
