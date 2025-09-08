# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Configuration for the Copilot Agent."""

import importlib.resources as pkg_resources
import os

from .utils.logger import logger

DATA_DIR = pkg_resources.files('copilot_agent.data')
PROMPT_DIR = pkg_resources.files('copilot_agent.prompts')
SQLDB_DIR = pkg_resources.files('copilot_agent.data.sqldb')

# set version, ["p0", "ga"]
COPILOT_VERSION = os.getenv('COPILOT_VERSION', '').lower()
# set agent cross talk
AGENT_PORT = int(os.getenv('AGENT_PORT', '50000'))
AGENT_MODE_LOCAL = os.getenv('AGENT_MODE', '').lower() == 'local'
AGENT_MODE_CA_LOCAL = os.getenv('AGENT_MODE_CA', '').lower() == 'local'
#
TO_CONTROLLER = True
#
TOKEN_LIMIT = 131072  # Default for GPT-4o
# "azure/gpt-4-32k ", TOKEN_LIMIT = 32768
# "azure/gpt-4o", TOKEN_LIMIT = 131072
DEBUG = False


def print_env_variables():
    """Prints the values of key environment variables."""
    logger.info(f"Env Var: COPILOT_VERSION: {os.getenv('COPILOT_VERSION', 'na')}")
    logger.info(f"Env Var: AGENT_PORT: {os.getenv('AGENT_PORT', '50000')}")
    logger.info(f"Env Var: AGENT_MODE: {os.getenv('AGENT_MODE', 'na')}")
    logger.info(f"Env Var: AGENT_MODE_CA: {os.getenv('AGENT_MODE_CA', 'na')}")
