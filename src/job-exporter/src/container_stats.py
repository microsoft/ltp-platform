#!/usr/bin/env python3

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import logging
import re
import subprocess

import utils

logger = logging.getLogger(__name__)

def parse_percentile(data: str):
    return float(data.replace("%", ""))

def parse_io(data: str):
    inOut = data.split("/")
    inByte = convert_to_byte(inOut[0])
    outByte = convert_to_byte(inOut[1])
    return {"in": inByte, "out": outByte}

def parse_usage_limit(data: str):
    usageLimit = data.split("/")
    usageByte = convert_to_byte(usageLimit[0])
    limitByte = convert_to_byte(usageLimit[1])
    return {"usage": usageByte, "limit": limitByte}

def parse_name(name: str):
    name = name.replace("k8s://", "")
    # Split the remaining string by '/'
    names = name.split("/")
    if len(names) == 3:
        return {"namespace": names[0], "pod": names[1], "container": names[2]}
    elif len(names) == 2:
        return {"namespace": names[0], "pod": names[1]}

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
    elif "eib" in data:
        return number * 2 ** 60
    elif "pib" in data:
        return number * 2 ** 50
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

def parse_nerdctl_stats(stats: str):
    lines = stats.strip().splitlines()
    container_stats = {}

    for data in lines:
        obj = json.loads(data)
        id = obj["ID"]
        containerInfo = {
            "id": obj["ID"],
            "name": parse_name(obj["Name"]),
            "cpuPerc": parse_percentile(obj["CPUPerc"]),
            "memPerc": parse_percentile(obj["MemPerc"]),
            "memUsage": parse_usage_limit(obj["MemUsage"]),
            "netIO": parse_io(obj["NetIO"]),
            "blockIO": parse_io(obj["BlockIO"]),
        }
        container_stats[id] = containerInfo
    return container_stats

def stats(histogram, timeout):
    try:
        result = utils.exec_cmd(
            ["nerdctl", "stats", "--no-stream", "--no-trunc", "--namespace", "k8s.io", "--format", "{{json .}}"],
            histogram=histogram,
            timeout=timeout)
        return parse_nerdctl_stats(result)
    except subprocess.CalledProcessError as e:
        logger.error("command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
    except subprocess.TimeoutExpired:
        logger.warning("docker stats timeout")
    except Exception:
        logger.exception("exec docker stats error")
