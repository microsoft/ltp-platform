#!/usr/bin/python

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

import argparse
import logging
import os
import sys

import yaml
import shutil


LOGGER = logging.getLogger(__name__)


sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.utils import init_logger  #pylint: disable=wrong-import-position


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("job_file", help="yaml file which contains job info")
    args = parser.parse_args()

    logging.info("Starting to process job file %s", args.job_file)
    if not os.path.isfile(args.job_file):
        logging.error("Job file %s does not exist", args.job_file)
        sys.exit(0)
    else:
        with open(args.job_file) as f:
            job_spec = yaml.safe_load(f.read())

    storage_config_names = []
    names = []
    try:
        storage_config_names = job_spec.get("extras", {}) \
            .get("com.microsoft.pai.runtimeplugin", [])
        for plugin in storage_config_names:
            if plugin.get("plugin") == "teamwise_storage":
                names = plugin.get("parameters", {}).get("storageConfigNames", [])
                logging.info("storageConfigNames: %s", names)
                break
    except Exception as e:
        logging.error("Failed to extract storageConfigNames: %s", str(e))

    for name in names:
        if name.startswith("blob-"):
            folder_name = f"/host-mnt/blobfusecache-{name[5:]}"
            if os.path.isdir(folder_name):
                for filename in os.listdir(folder_name):
                    file_path = os.path.join(folder_name, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        logging.error("Failed to delete %s. Reason: %s", file_path, str(e))
            else:
                logging.warning("%s does not exist.", folder_name)

if __name__ == "__main__":
    init_logger()
    main()
