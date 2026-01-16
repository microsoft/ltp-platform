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
FROM golang:1.24 AS gosu

WORKDIR /src

RUN git clone --branch 1.19 --depth 1 https://github.com/tianon/gosu.git .

RUN go mod edit -go=1.24 \
 && go mod edit -toolchain=go1.24.0 \
 && go mod tidy -compat=1.24

RUN go get -u ./... && go mod tidy -compat=1.24

RUN go mod download

RUN CGO_ENABLED=0 go build \
    -trimpath -buildvcs=false -ldflags="-s -w" \
    -o /usr/local/bin/gosu .

FROM postgres:16.8

RUN apt update && apt upgrade -y

RUN mkdir -p /docker-entrypoint-initdb.d

COPY --from=gosu /usr/local/bin/gosu /usr/local/bin/gosu

COPY src/once_init_table.sql /docker-entrypoint-initdb.d
