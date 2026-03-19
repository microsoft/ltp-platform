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

import logging
import logging.config


import sys
import os
import subprocess
import yaml


class DockerClient:

    def __init__(self, docker_registry, docker_namespace, docker_username, docker_password, managed_identity_id=None):

        docker_registry = "" if docker_registry == "public" else docker_registry

        self.docker_registry = docker_registry
        self.docker_namespace = docker_namespace
        self.docker_username = docker_username
        self.docker_password = docker_password
        self.managed_identity_id = managed_identity_id

        self.docker_login()


    def set_build_cache_type(self, build_nocache=False):
        self.build_nocache = build_nocache

    def resolve_image_name(self, image_name):
        prefix = "" if self.docker_registry == "" else self.docker_registry + "/"
        return "{0}{1}/{2}".format(prefix, self.docker_namespace, image_name)



    def docker_login(self):
        if self.docker_username and self.docker_password:
            shell_cmd = "docker login -u {0} -p {1} {2}".format(self.docker_username, self.docker_password, self.docker_registry)
            execute_shell(shell_cmd)
        else:
            # Check if already logged in to Azure CLI
            try:
                logger.info("Checking Azure CLI login status...")
                subprocess.check_output("az account show", shell=True, stderr=subprocess.STDOUT)
                logger.info("Azure CLI is already logged in")
            except subprocess.CalledProcessError:
                logger.info("Azure CLI not logged in, initiating login...")
                if self.managed_identity_id:
                    # Login with managed identity
                    shell_cmd = "az login --identity --username {0}".format(self.managed_identity_id)
                    logger.info("Logging in with managed identity: {0}".format(self.managed_identity_id))
                else:
                    # Interactive login with user account
                    shell_cmd = "az login"
                    logger.info("Initiating interactive Azure login...")
                execute_shell(shell_cmd)

            # Check if ACR exists in current subscription before attempting login
            # Extract registry name without .azurecr.io suffix
            registry_name = self.docker_registry.replace('.azurecr.io', '')
            check_cmd = "az acr show --name {0}".format(registry_name)

            try:
                logger.info("Checking if ACR '{0}' exists in current subscription...".format(registry_name))
                subprocess.run(
                    check_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True
                )
                logger.info("ACR '{0}' found in current subscription".format(registry_name))
            except subprocess.TimeoutExpired:
                logger.error("Command timed out: {0}".format(check_cmd))
                logger.error("Failed to check ACR existence within 10 seconds")
                sys.exit(1)
            except subprocess.CalledProcessError as e:
                logger.error("ACR '{0}' not found in current subscription".format(registry_name))
                if e.stderr:
                    logger.error("Error details: {0}".format(e.stderr.strip()))
                logger.error("")
                logger.error("Please check:")
                logger.error("  1. The ACR registry name is correct")
                logger.error("  2. You are using the correct Azure subscription")
                logger.error("")
                logger.error("Current subscription can be checked with: az account show")
                logger.error("To switch subscription, use: az account set --subscription <subscription-id>")
                sys.exit(1)

            # Login to Azure Container Registry
            shell_cmd = "az acr login --name {0}".format(registry_name)
            try:
                logger.info("Logging in to ACR '{0}'...".format(registry_name))
                subprocess.run(
                    shell_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True
                )
                logger.info("Successfully logged in to ACR '{0}'".format(registry_name))
            except subprocess.TimeoutExpired:
                logger.error("Command timed out: {0}".format(shell_cmd))
                logger.error("ACR login command exceeded 30 seconds timeout")
                sys.exit(1)
            except subprocess.CalledProcessError as e:
                logger.error("Failed to login to ACR '{0}'".format(registry_name))
                if e.stderr:
                    logger.error("Error details: {0}".format(e.stderr.strip()))
                logger.error("Please check your permissions to access this ACR registry")
                sys.exit(1)


    def docker_image_build(self, image_name, dockerfile_path, build_path):
        if self.build_nocache:
            cmd = "docker build --no-cache -t {0} -f {1} {2}".format(image_name, dockerfile_path, build_path)
        else:
            cmd = "docker build -t {0} -f {1} {2}".format(image_name, dockerfile_path, build_path)
        execute_shell(cmd)


    def docker_image_tag(self, origin_image_name, image_tag):
        origin_tag = origin_image_name
        target_tag = "{0}:{1}".format(self.resolve_image_name(origin_image_name), image_tag)
        cmd = "docker tag {0} {1}".format(origin_tag, target_tag)
        execute_shell(cmd)



    def docker_image_push(self, image_name, image_tag):
        target_tag = "{0}:{1}".format(self.resolve_image_name(image_name), image_tag)
        cmd = "docker push {0}".format(target_tag)
        execute_shell(cmd)

def setup_logger_config(logger):
    """
    Setup logging configuration.
    """
    if len(logger.handlers) == 0:
        logger.propagate = False
        logger.setLevel(logging.DEBUG)
        consoleHandler = logging.StreamHandler()
        consoleHandler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        consoleHandler.setFormatter(formatter)
        logger.addHandler(consoleHandler)

logger = logging.getLogger(__name__)
setup_logger_config(logger)

def execute_shell(shell_cmd):
    try:
        logger.info("Begin to execute the command: {0}".format(shell_cmd))
        subprocess.check_call( shell_cmd, shell=True )
        logger.info("Executing command successfully: {0}".format(shell_cmd))
    except subprocess.CalledProcessError:
        logger.error("Executing command failed: {0}".format(shell_cmd))
        sys.exit(1)



def execute_shell_with_output(shell_cmd):
    try:
        logger.info("Begin to execute the command: {0}".format(shell_cmd))
        res = subprocess.check_output( shell_cmd, shell=True )
        logger.info("Executes command successfully: {0}".format(shell_cmd))
    except subprocess.CalledProcessError:
        logger.error("Executes command failed: {0}".format(shell_cmd))
        sys.exit(1)

    return res

def load_yaml_config(config_path):

    if not os.path.exists(config_path):
        logger.error("Invalid config path: {0}".format(config_path))
        sys.exit(1)

    with open(config_path, "r") as f:
        cluster_data = yaml.safe_load(f)

    return cluster_data
