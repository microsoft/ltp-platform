# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import platform

LOGGER = logging.getLogger(__name__)

if platform.uname().machine == "x86_64":
    import amdsmi
else:
    LOGGER.warning("AMD SMI does not support arm64 or aarch64, skipped import")


def init_amd_smi():
    try:
        amdsmi.amdsmi_init()
        return amdsmi.amdsmi_get_processor_handles()
    except (amdsmi.AmdSmiLibraryException, amdsmi.AmdSmiParameterException) as e:
        LOGGER.error("Failed to initialize AMD SMI: %s", e)
    except Exception as e:
        LOGGER.error("Unexpected error during AMD SMI initialization: %s", e)

    return None

def destroy_amd_smi():
    try:
        amdsmi.amdsmi_shut_down()
        return "amd smi shut down successfully"
    except (amdsmi.AmdSmiLibraryException, amdsmi.AmdSmiParameterException) as e:
        LOGGER.error("Failed to shut down AMD SMI: %s", e)
    except Exception as e:
        LOGGER.error("Unexpected error during AMD SMI shutdown: %s", e)
    
    return None

def get_processors_for_gpu():
    pids = {}
    procs = None
    try:
        procs = amdsmi.amdsmi_get_gpu_compute_process_info()
        if procs:
            for proc in procs:
                indices = amdsmi.amdsmi_get_gpu_compute_process_gpus(proc['process_id']) or []
                for index in indices:
                    if index not in pids:
                        pids[index] = []
                    pids[index].append(proc['process_id'])
    except (amdsmi.AmdSmiLibraryException, amdsmi.AmdSmiParameterException):
        LOGGER.error("Failed to get GPU compute process info due to AMD SMI exception")
    except Exception as e:
        LOGGER.error("Failed to get GPU compute process info: %s", e)
        if not procs:
            LOGGER.error("procs is empty")
        else:
            LOGGER.error("procs: %s", [proc.__dict__ for proc in procs])
    return pids


def get_device_ecc_error(device_handler):
    corrected_ecc = 0
    uncorrected_ecc = 0
    for block in amdsmi.AmdSmiGpuBlock:
        try:
            ecc_count = amdsmi.amdsmi_get_gpu_ecc_count(device_handler, block)
            corrected_ecc += ecc_count['correctable_count']
            uncorrected_ecc += ecc_count['uncorrectable_count']
        except (amdsmi.AmdSmiLibraryException, amdsmi.AmdSmiParameterException):
            LOGGER.warning('Failed to get ECC count for block: {}'.format(block))
        except Exception as err:
            LOGGER.warning('Get device ECC information failed: {}'.format(str(err)))

    return corrected_ecc, uncorrected_ecc
