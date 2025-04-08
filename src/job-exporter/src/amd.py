# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from dataclasses import dataclass
import json
import logging
import subprocess

import utils
import amd_smi_cmds


LOGGER = logging.getLogger(__name__)


class AMDGpuStatus(object):
    def __init__(self, gpu_util, gpu_mem_util, pids, ecc_errors, minor, uuid, temperature, pci_addr):
        self.gpu_util = gpu_util # float
        self.gpu_mem_util = gpu_mem_util # float
        self.pids = pids # list of int
        self.ecc_errors = ecc_errors # list of EccError
        self.minor = minor
        self.uuid = uuid # str
        self.temperature = temperature # None or float celsius
        self.pci_addr = pci_addr # str

    def __repr__(self):
        pids_str = f"[{', '.join(map(str, self.pids))}]" if self.pids else '[]'
        return "util: %.3f, mem_util: %.3f, pids: [%s], ecc: %s, minor: %s, uuid: %s, temperature: %.3f, pci_addr: %s" % \
            (self.gpu_util, self.gpu_mem_util, pids_str, self.ecc_errors, self.minor, self.uuid, self.temperature, self.pci_addr)

    def __eq__(self, o): # for test
        return self.gpu_util == o.gpu_util and \
                self.gpu_mem_util == o.gpu_mem_util and \
                self.pids == o.pids and \
                self.ecc_errors == o.ecc_errors and \
                self.minor == o.minor and \
                self.uuid == o.uuid and \
                self.temperature == o.temperature and \
                self.pci_addr == o.pci_addr


def rocm_smi(histogram, timeout, device_handlers, amd_smi_initialized):
    try:
        smi_output = utils.exec_cmd(
            ["rocm-smi", "--showmeminfo", "all", "-a", "--json"],
            histogram=histogram,
            timeout=timeout)
        
        ecc_errors = {}
        pids = {}

        if amd_smi_initialized:
            for index, handler in enumerate(device_handlers):
                corrected_ecc, uncorrected_ecc = utils.run_func_in_thread(
                    amd_smi_cmds.get_device_ecc_error, timeout, handler)
                ecc_errors[index] = utils.EccError(corrected_ecc, uncorrected_ecc)
                LOGGER.debug(f"corrected_ecc: {corrected_ecc}, uncorrected_ecc: {uncorrected_ecc}")
        
            pids = utils.run_func_in_thread(amd_smi_cmds.get_processors_for_gpu, timeout)
        else:
            LOGGER.exception("amd smi not initialized")
            raise RuntimeError("amd smi not initialized")

        return parse_smi_json_result(smi_output, ecc_errors, pids)
    except subprocess.CalledProcessError as e:
        LOGGER.exception("command '%s' return with error (code %d): %s", e.cmd,
                         e.returncode, e.output)
        
        raise e
    except subprocess.TimeoutExpired:
        LOGGER.warning("rocm-smi timeout")
        raise TimeoutError
    except Exception as e:
        LOGGER.exception("exec rocm-smi error: %s", str(e))
        raise


def parse_smi_json_result(smi_output, ecc_errors, pids):
    """ return a map, key is PCI bus index, value is AMDGpuStatus """
    res = {}
    output = json.loads(smi_output)
    gpu_infos = {int(k[4:]): v for k, v in output.items() if k.startswith("card")}

    for index, value in gpu_infos.items():
        gpu_util = float(value["GPU use (%)"])
        gpu_mem_vram_total = float(value["VRAM Total Memory (B)"])
        gpu_mem_vram_used = float(value["VRAM Total Used Memory (B)"])
        gpu_mem_vram_util = gpu_mem_vram_used / gpu_mem_vram_total * 100
        # Change to Sensor Edge in future.
        # refer: https://rocm.docs.amd.com/projects/rocm_smi_lib/en/latest/doxygen/html/rocm__smi_8h.html#af4ad084051b497ddf4afccc50639de7e
        gpu_temperature = float(value["Temperature (Sensor junction) (C)"])
        gpu_uuid = str(value["Unique ID"]).strip()
        pci_addr = value["PCI Bus"]
        pid = pids.get(index, []) if pids else []

        res[str(index)] = AMDGpuStatus(gpu_util, gpu_mem_vram_util, pid, ecc_errors[index], str(index),
                           gpu_uuid, gpu_temperature, pci_addr)

    return res