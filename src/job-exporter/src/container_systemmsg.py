#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import logging
import datetime
import subprocess

import utils

logger = logging.getLogger(__name__)

def parse_system_msg_stats(stats: str):
    lines = stats.strip().splitlines()
    system_msgs = set()
    for data in lines:
        if "no-retry page fault" in data:
            system_msgs.add("no-retry page fault")
        if "amdgpu: trn=2 ACK should not assert! wait again !" in data:
            system_msgs.add("amdgpu: trn=2 ACK should not assert! wait again !")
        if "Fence fallback timer expired on ring sdma" in data:
            system_msgs.add("Fence fallback timer expired on ring sdma")
        if "GPU reset" in data:
            system_msgs.add("GPU reset")
        if "segfault" in data and "python" not in data:
            system_msgs.add("segfault")
    
    return system_msgs

def stats(histogram, timeout, duration):
    since_time = (datetime.datetime.now() - datetime.timedelta(minutes=duration)).strftime('%Y-%m-%d %H:%M:%S')
    try:
        result = utils.exec_cmd(
            ["dmesg", "--ctime", "--since", since_time],
            histogram=histogram,
            timeout=timeout)
        return parse_system_msg_stats(result)
    except subprocess.CalledProcessError as e:
        logger.error("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
    except subprocess.TimeoutExpired:
        logger.warning("getting dmesg timeout")
    except Exception:
        logger.exception("getting dmesg error")
