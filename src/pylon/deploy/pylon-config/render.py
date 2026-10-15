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

import os
from hashlib import md5
from urllib.parse import urlsplit
from jinja2 import Template

env = {}
for key in os.environ:
    env[key] = os.environ[key]

if env.get('MODEL_PROXY_URI'):
    model_proxy = urlsplit(env['MODEL_PROXY_URI'])
    if (model_proxy.scheme not in ('http', 'https') or not model_proxy.hostname
            or model_proxy.username is not None or model_proxy.password is not None
            or model_proxy.query or model_proxy.fragment):
        raise ValueError('MODEL_PROXY_URI must be an HTTP(S) URL without credentials, query, or fragment')
    model_proxy_port = model_proxy.port
    if model_proxy_port is None:
        model_proxy_port = 443 if model_proxy.scheme == 'https' else 80
    model_proxy_host = model_proxy.hostname
    if ':' in model_proxy_host:
        model_proxy_host = '[{}]'.format(model_proxy_host)
    env['MODEL_PROXY_UPSTREAM_SCHEME'] = model_proxy.scheme
    env['MODEL_PROXY_UPSTREAM_ADDRESS'] = '{}:{}'.format(model_proxy_host, model_proxy_port)
    env['MODEL_PROXY_UPSTREAM_HOST'] = model_proxy.hostname
    env['MODEL_PROXY_UPSTREAM_PATH'] = model_proxy.path.rstrip('/')

templateString = open('/pylon-config/nginx.conf.template', 'r').read()
locationCfgTemplateString = open('/pylon-config/location.conf.template', 'r').read()

env.setdefault('PYLON_CONF_ETAG', md5(templateString.encode('utf-8')).hexdigest())

renderedString = Template(templateString).render(env)
open('/root/nginx.conf', 'w').write(renderedString)

locationCfgRenderedString = Template(locationCfgTemplateString).render(env)
open('/root/location.conf', 'w').write(locationCfgRenderedString)
