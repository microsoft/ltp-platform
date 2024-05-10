# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import subprocess
import json
import logging

import utils
from utils import GpuVendor

logger = logging.getLogger(__name__)

class InspectResult(object):
    """ Represents a task meta data, parsed from crictl inspect result """
    def __init__(self, username, job_name, role_name, task_index, gpu_ids, job_instance_id, virtual_cluster, pid):
        self.username = username
        self.job_name = job_name
        self.role_name = role_name
        self.task_index = task_index
        self.gpu_ids = gpu_ids # comma separated str, str may be minor_number or UUID
        self.job_instance_id = job_instance_id # Used to distinguish job instance with same name but different retry number.
        self.virtual_cluster = virtual_cluster
        self.pid = pid

    def __repr__(self):
        return "username %s, job_name %s, role_name %s, task_index %s, gpu_ids %s, job_instance_id %s virtual_cluster %s pid %s " % \
                (self.username, self.job_name, self.role_name, self.task_index, self.gpu_ids, self.job_instance_id, self.virtual_cluster, self.pid)

    def __eq__(self, o):
        return self.username == o.username and \
                self.job_name == o.job_name and \
                self.role_name == o.role_name and \
                self.task_index == o.task_index and \
                self.gpu_ids == o.gpu_ids and \
                self.job_instance_id == o.job_instance_id and \
                self.virtual_cluster == o.virtual_cluster and \
                self.pid == o.pid


keys = {"PAI_JOB_NAME", "PAI_USER_NAME", "PAI_CURRENT_TASK_ROLE_NAME", "GPU_ID",
        "PAI_TASK_INDEX", "DLWS_JOB_ID", "DLWS_USER_NAME", "PAI_VIRTUAL_CLUSTER"}


def parse_crictl_inspect(inspect_output, gpu_vender):
    obj = json.loads(inspect_output)

    m = {}

    obj_labels = utils.walk_json_field_safe(obj, "status", "labels")
    if obj_labels is not None:
        for k, v in obj_labels.items():
            if k in keys:
                m[k] = v

    obj_env = utils.walk_json_field_safe(obj, "info", "config", "envs")
    if obj_env:
        for env in obj_env:
            if env["key"] in keys:
                m[env["key"]] = env["value"]

            # for kube-launcher tasks
            if k == "FC_TASK_INDEX":
                m["PAI_TASK_INDEX"] = v
            else:
                if k == "NVIDIA_VISIBLE_DEVICES" and gpu_vender == GpuVendor.NVIDIA and v \
                    and v != "all" and v != "void" and v != "none":
                    m["GPU_ID"] = v
                if k == "PAI_AMD_VISIBLE_DEVICES" and gpu_vender == GpuVendor.AMD and v:
                    m["GPU_ID"] = v

            if k == "FC_FRAMEWORK_ATTEMPT_INSTANCE_UID" or k == "APP_ID":
                m["JOB_INSTANCE_ID"] = v

    pid = utils.walk_json_field_safe(obj, "info", "pid")

    return InspectResult(
            m.get("PAI_USER_NAME") or m.get("DLWS_USER_NAME"),
            m.get("PAI_JOB_NAME") or m.get("DLWS_JOB_ID"),
            m.get("PAI_CURRENT_TASK_ROLE_NAME"),
            m.get("PAI_TASK_INDEX"),
            m.get("GPU_ID"),
            m.get("JOB_INSTANCE_ID"),
            m.get("PAI_VIRTUAL_CLUSTER"),
            pid)

def inspect(container_id, histogram, timeout, gpu_vender):
    try:
        result = utils.exec_cmd(
                ["crictl", "inspect", container_id],
                histogram=histogram,
                timeout=timeout)
        return parse_crictl_inspect(result, gpu_vender)
    except subprocess.CalledProcessError as e:
        logger.exception("command '%s' return with error (code %d): %s",
                e.cmd, e.returncode, e.output)
    except subprocess.TimeoutExpired:
        logger.warning("docker inspect timeout")
    except Exception:
        logger.exception("exec docker inspect error")
