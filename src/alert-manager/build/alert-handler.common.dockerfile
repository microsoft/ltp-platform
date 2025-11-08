# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM node:20

RUN npm install -g npm@latest

RUN apt update && apt upgrade -y

RUN apt purge -y subversion && apt autoremove -y

WORKDIR /usr/src/app

ENV NODE_ENV=production

COPY ./src/alert-handler .

RUN corepack enable && corepack install -g yarn@4.2.2
RUN yarn install

# install python and dependencies
RUN apt-get install -y python3-pip
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages

ENTRYPOINT ["npm", "start"]
