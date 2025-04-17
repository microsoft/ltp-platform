# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import subprocess
import logging
import os

import utils


IB_FILE_PATH = "/sys/class/infiniband"

IB_COUNTERS = [
    'port_xmit_data',
    'port_rcv_data',
    'port_xmit_discards',
    'port_rcv_errors',
    'port_xmit_constraint_errors',
    'port_rcv_constraint_errors',
    'port_physical_state',
]

PORT_STATE = {
    'Polling': 0,
    'LinkUp': 1
}

def stats(container_id, histogram, timeout):
    result = {}
    try:
        hca_list = list_files(container_id, IB_FILE_PATH, histogram, timeout)
        if not hca_list:
            return result
        for hca in hca_list:
            port_path = str(os.path.join(IB_FILE_PATH, hca, 'ports'))
            ports = list_files(container_id, port_path, histogram, timeout)
            if not ports:
                continue
            for port in ports:
                counter_path = str(os.path.join(IB_FILE_PATH, hca, 'ports', port, 'counters'))
                result['{}:{}'.format(hca, port)] = {}
                for field_name in IB_COUNTERS:
                    if field_name == 'port_physical_state':
                        state_path = str(os.path.join(IB_FILE_PATH, hca, 'ports', port, 'phys_state'))
                        state_content = get_file_content(container_id, state_path, histogram, timeout)
                        if state_content:
                            state = PORT_STATE.get(state_content.split()[1].strip(), None)
                            if state is not None:
                                result['{}:{}'.format(hca, port)][field_name] = state
                            else:
                                result['{}:{}'.format(hca, port)][field_name] = -1
                                logging.warning("Invalid port state value for %s: %s", state_path, state_content)
                        continue

                    count_file_path = str(os.path.join(counter_path, field_name))
                    counter_content = get_file_content(container_id, count_file_path, histogram, timeout)
                    if counter_content:
                        try:
                            counter = int(counter_content.strip())
                            result['{}:{}'.format(hca, port)][field_name] = counter
                        except ValueError:
                            logging.warning("Invalid counter value for %s: %s", count_file_path, counter_content)
    except Exception:
        logging.exception("Error while collecting IB stats")
    return result

def list_files(container_id, path, histogram, timeout):
    try:
        result = utils.exec_cmd(
            ["nerdctl", "exec", "--namespace", "k8s.io", container_id,  "ls", path],
            histogram=histogram,
            timeout=timeout)
        logging.debug("List of files at %s: %s", path, result)
        file_list = result.split('\n')
        return [file for file in file_list if file]
    except subprocess.CalledProcessError as e:
        logging.exception("command '%s' return with error (code %d): %s",
                e.cmd, e.returncode, e.output)
    except subprocess.TimeoutExpired:
        logging.warning("nerdctl exec timeout for command: nerdctl exec %s ls %s", container_id, path)
    except Exception:
        logging.exception("exec nerdctl exec error for command: nerdctl exec %s ls %s", container_id, path)

def get_file_content(container_id, path, histogram, timeout):
    try:
        result = utils.exec_cmd(
            ["nerdctl", "exec", "--namespace", "k8s.io", container_id,  "cat", path],
            histogram=histogram,
            timeout=timeout)
        logging.debug("File content at %s: %s", path, result)
        return result
    except subprocess.CalledProcessError as e:
        logging.exception("command '%s' return with error (code %d): %s",
                e.cmd, e.returncode, e.output)
    except subprocess.TimeoutExpired:
        logging.warning("nerdctl exec timeout for command: nerdctl exec %s cat %s", container_id, path)
    except Exception:
        logging.exception("exec nerdctl exec error for command: nerdctl exec %s cat %s", container_id, path)
