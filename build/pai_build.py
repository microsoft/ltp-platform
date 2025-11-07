#!/usr/bin/env python
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


from core import build_center
from core import build_utility
from model import config_model


import os
import sys
import argparse
import datetime
import logging
import logging.config

logger = logging.getLogger(__name__)


def load_build_config(config_dir):
    buildConfig = config_model.ConfigModel(config_dir)
    configModel = buildConfig.build_config_parse()
    return configModel


def build_service(args, config_model):
    pai_build = build_center.BuildCenter(config_model, args.service, 'k8s', args)
    pai_build.set_build_cache_type(args.nocache)
    pai_build.build_center()


def push_image(args, config_model):
    if args.service is not None:
        if args.imagelist is None:
            args.imagelist = []
        temp = build_center.BuildCenter(config_model, None, 'k8s')
        temp.construct_graph()
        all_services = temp.graph.services
        for service in args.service:
            if service in all_services:
                if all_services[service].docker_files:
                    for docker_file in all_services[service].docker_files:
                        image = os.path.splitext(docker_file)[0]
                        args.imagelist.append(image)
                else:
                    logger.warning(
                        "Service {0} has no images found".format(service))
            else:
                logger.warning(
                    "Service {0} has no images found".format(service))
    pai_push = build_center.BuildCenter(config_model, args.imagelist, 'k8s')
    pai_push.push_center()


def main():

    # Define execution path to root folder
    scriptFolder = os.path.dirname(os.path.realpath(__file__))
    os.chdir(os.path.dirname(scriptFolder))

    starttime = datetime.datetime.now()
    parser = argparse.ArgumentParser(description="pai build client")
    logger.info("Pai build starts at {0}".format(starttime))

    subparsers = parser.add_subparsers(help='build service cli')

    # Build commands
    build_parser = subparsers.add_parser('build', help='build service cli')
    build_parser.add_argument(
        '-c', '--config',
        type=str,
        required=True,
        help='The path of your configuration directory.'
    )
    build_parser.add_argument(
        '-s', '--service',
        type=str,
        nargs='+',
        help="The service list you want to build"
    )
    build_parser.add_argument(
        '-n', '--nocache',
        action='store_true',
        help="Build the service using cache or not"
    )
    build_parser.add_argument(
        '-i', '--imagelist',
        type=str,
        nargs='+',
        default=None,
        help="The image list you want to build"
    )
    build_parser.set_defaults(func=build_service)

    # Push commands
    push_parser = subparsers.add_parser('push', help='push image cli')
    push_parser.add_argument(
        '-c', '--config',
        type=str,
        required=True,
        help='The path of your configuration directory.'
    )
    push_parser.add_argument(
        '-i', '--imagelist',
        type=str,
        nargs='+',
        help="The image list you want to push"
    )
    push_parser.add_argument(
        '-s', '--service',
        type=str,
        nargs='+',
        help="The service list that contains corresponding images you want to push"
    )
    push_parser.add_argument(
        '--docker-registry',
        type=str,
        help="The docker registry you want to push to, which will override the config file"
    )
    push_parser.add_argument(
        "--docker-namespace",
        type=str,
        help="The docker namespace you want to push to, which will override the config file if '--docker-registry' is also set"
    )
    push_parser.add_argument(
        '--docker-username',
        type=str,
        help="The docker username you want to use for authentication, which will override the config file if '--docker-registry' is also set"
    )
    push_parser.add_argument(
        '--docker-password',
        type=str,
        help="The docker password you want to use for authentication, which will override the config file if '--docker-registry' is also set"
    )
    push_parser.add_argument(
        "--docker-tag",
        type=str,
        help="The docker tag you want to push to, which will override the config file if '--docker-registry' is also set"
    )
    push_parser.set_defaults(func=push_image)

    args = parser.parse_args()
    config_model = load_build_config(args.config)
    if hasattr(args, 'docker_registry') and args.docker_registry is not None:
        config_model['dockerRegistryInfo']['dockerRegistryDomain'] = args.docker_registry
        if args.docker_namespace is not None:
            config_model['dockerRegistryInfo']['dockerNameSpace'] = args.docker_namespace
        if args.docker_username is not None:
            config_model['dockerRegistryInfo']['dockerUserName'] = args.docker_username
        if args.docker_password is not None:
            config_model['dockerRegistryInfo']['dockerPassword'] = args.docker_password
        if args.docker_tag is not None:
            config_model['dockerRegistryInfo']['dockerTag'] = args.docker_tag
    
    args.func(args, config_model)

    endtime = datetime.datetime.now()
    logger.info("Pai build ends at {0}".format(endtime))
    logger.info("Pai build costs {0}".format(endtime - starttime))


if __name__ == "__main__":
    build_utility.setup_logger_config(logger)
    main()
