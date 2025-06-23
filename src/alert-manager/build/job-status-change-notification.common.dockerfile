# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM node:20

RUN npm install -g npm@latest

WORKDIR /usr/src/app

RUN apt update && apt upgrade -y

ENV NODE_ENV=production

COPY ./src/job-status-change-notification .

RUN corepack enable && corepack install -g yarn@4.2.2
RUN yarn install

ENTRYPOINT ["npm", "start"]
