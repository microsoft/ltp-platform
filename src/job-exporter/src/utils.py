#!/usr/bin/env python3
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

from enum import Enum
import os
import subprocess

import logging

import threading
import queue

logger = logging.getLogger(__name__)


def run_func_in_thread(func, timeout, *args, **kwargs):
    if not callable(func):
        raise ValueError("The 'func' parameter must be a callable function.")

    result_queue = queue.Queue()

    def target():
        try:
            result = func(*args, **kwargs)
            result_queue.put(result)
        except Exception as e:
            logger.warning("run function %s encountered an error: %s", func.__name__, str(e))
            result_queue.put(None)

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError(f"Function {func.__name__} did not complete within {timeout} seconds.")
    return result_queue.get()


def exec_cmd(*args, **kwargs):
    """ exec a cmd with timeout, also record time used using prometheus higtogram """
    if kwargs.get("histogram") is not None:
        histogram = kwargs.pop("histogram")
    else:
        histogram = None

    logger.debug("about to exec %s", args[0])

    if histogram is not None:
        with histogram.time():
            return subprocess.check_output(*args, **kwargs).decode("utf-8")
    else:
        return subprocess.check_output(*args, **kwargs).decode("utf-8")


def walk_json_field_safe(obj, *fields):
    """ for example a=[{"a": {"b": 2}}]
    walk_json_field_safe(a, 0, "a", "b") will get 2
    walk_json_field_safe(a, 0, "not_exist") will get None
    """
    try:
        for f in fields:
            obj = obj[f]
        return obj
    except:
        return None


class EccError(object):
    """ EccError represents volatile count from one GPU card,
    see https://developer.download.nvidia.com/compute/DCGM/docs/nvidia-smi-367.38.pdf for more info """
    def __init__(self, single=0, double=0):
        self.single = single
        self.double = double

    def __repr__(self):
        return "s: %d, d: %d" % (self.single, self.double)

    def __eq__(self, o):
        return self.single == o.single and \
                self.double == o.double


class GpuVendor(Enum):
    UNKNOWN = "unknown"
    NVIDIA = "nvidia"
    AMD = "amd"

def get_gpu_vendor():
    nvidia_device_path = "/dev/nvidiactl"
    amd_device_path = "/dev/kfd"
    if os.path.exists(nvidia_device_path):
        return GpuVendor.NVIDIA
    if os.path.exists(amd_device_path):
        return GpuVendor.AMD
    return GpuVendor.UNKNOWN
