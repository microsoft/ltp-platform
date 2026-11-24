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

FROM openresty/openresty:1.31.8.1-jammy AS openresty-builder

# Backport the upstream HTTP/2 fixes until OpenResty ships a patched release.
COPY build/CVE-2026-123007-CVE-2026-123633.patch /tmp/http2-security.patch
RUN cd /tmp && \
    curl -fsSL https://openresty.org/download/openresty-1.31.8.1.tar.gz -o openresty.tar.gz && \
    echo 'b569c63b420f80a4ac8466f2deffe73ed93ab760026532e039c3658409a997f4  openresty.tar.gz' | sha256sum -c - && \
    tar xzf openresty.tar.gz && \
    cd openresty-1.31.8.1/bundle/nginx-1.31.8 && \
    patch --batch --fuzz=0 -p1 < /tmp/http2-security.patch && \
    cd ../.. && \
    ./configure -j2 \
        --prefix=/usr/local/openresty \
        --with-luajit=/usr/local/openresty/luajit \
        --build=ltp-CVE-2026-123007-CVE-2026-123633 \
        --with-cc-opt='-O2 -DNGX_LUA_ABORT_AT_PANIC -I/usr/local/openresty/pcre2/include -I/usr/local/openresty/openssl3/include' \
        --with-ld-opt='-L/usr/local/openresty/pcre2/lib -L/usr/local/openresty/openssl3/lib -Wl,-rpath,/usr/local/openresty/pcre2/lib:/usr/local/openresty/openssl3/lib' \
        --with-pcre \
        --with-pcre-jit \
        --with-compat \
        --without-http_rds_json_module \
        --without-http_rds_csv_module \
        --without-lua_rds_parser \
        --without-mail_pop3_module \
        --without-mail_imap_module \
        --without-mail_smtp_module \
        --with-http_addition_module \
        --with-http_auth_request_module \
        --with-http_dav_module \
        --with-http_flv_module \
        --with-http_geoip_module=dynamic \
        --with-http_gunzip_module \
        --with-http_gzip_static_module \
        --with-http_image_filter_module=dynamic \
        --with-http_mp4_module \
        --with-http_random_index_module \
        --with-http_realip_module \
        --with-http_secure_link_module \
        --with-http_slice_module \
        --with-http_ssl_module \
        --with-http_stub_status_module \
        --with-http_sub_module \
        --with-http_v2_module \
        --with-http_v3_module \
        --with-http_xslt_module=dynamic \
        --with-ipv6 \
        --with-mail \
        --with-mail_ssl_module \
        --with-md5-asm \
        --with-sha1-asm \
        --with-stream \
        --with-stream_ssl_module \
        --with-stream_ssl_preread_module \
        --with-threads && \
    make -j2 && \
    make install

FROM openresty/openresty:1.31.8.1-jammy

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get upgrade -y && \
    apt-get install -y systemd && \
    # LuaRocks modules you need
    luarocks install lua-cjson && \
    luarocks install luafilesystem && \
    luarocks install lua-path && \
    luarocks install lua-resty-openssl && \
    luarocks install lua-resty-string && \
    luarocks install lua-resty-jwt && \
    # clean apt cache to keep image slim
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy after package installation so upgrades cannot restore the old binary.
COPY --from=openresty-builder /usr/local/openresty/nginx/sbin/nginx /usr/local/openresty/nginx/sbin/nginx
COPY --from=openresty-builder /usr/local/openresty/nginx/modules/ /usr/local/openresty/nginx/modules/

COPY src/nginx/nginx.conf.default /etc/nginx/conf.d/default.conf
COPY src/nginx/nginx.conf /usr/local/openresty/nginx/conf/nginx.conf
COPY src/nginx/*.lua /etc/nginx/lua/
