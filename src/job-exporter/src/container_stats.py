#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import subprocess
import re
import logging

import utils

logger = logging.getLogger(__name__)

def parse_percentile(data):
    return float(data.replace("%", ""))

def parse_io(data):
    inOut = data.split("/")
    inByte = convert_to_byte(inOut[0])
    outByte = convert_to_byte(inOut[1])
    return {"in": inByte, "out": outByte}

def parse_usage_limit(data):
    usageLimit = data.split("/")
    usageByte = convert_to_byte(usageLimit[0])
    limitByte = convert_to_byte(usageLimit[1])
    return {"usage": usageByte, "limit": limitByte}

def convert_to_byte(data):
    data = data.lower()
    number = float(re.findall(r"[0-9.]+", data)[0])
    if "tb" in data:
        return number * 10 ** 12
    elif "gb" in data:
        return number * 10 ** 9
    elif "mb" in data:
        return number * 10 ** 6
    elif "kb" in data:
        return number * 10 ** 3
    elif "tib" in data:
        return number * 2 ** 40
    elif "gib" in data:
        return number * 2 ** 30
    elif "mib" in data:
        return number * 2 ** 20
    elif "kib" in data:
        return number * 2 ** 10
    else:
        return number

def parse_crictl_stats(stats):
    data = [line.split() for line in stats.splitlines()]
    # pop the headers
    data.pop(0)
    row_count = len(data)
    container_stats = {}

    for i in range(row_count):
        id = data[i][0]
        containerInfo = {
            "id": data[i][0],
            "name": data[i][1],
            "CPUPerc": parse_percentile(data[i][2]),
            "MemUsageByte": convert_to_byte(data[i][3]),
            "DiskUsageByte": convert_to_byte(data[i][4]),
            "Inodes": int(data[i][5])
        }
        container_stats[id] = containerInfo
    return container_stats

def stats(histogram, timeout):
    try:
        result = utils.exec_cmd(
            ["crictl", "stats", "-o", "table"],
            histogram=histogram,
            timeout=timeout)
        return parse_crictl_stats(result)
    except subprocess.CalledProcessError as e:
        logger.error("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
    except subprocess.TimeoutExpired:
        logger.warning("docker stats timeout")
    except Exception:
        logger.exception("exec docker stats error")
