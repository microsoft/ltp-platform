#!/usr/bin/env python3

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


import copy


class CopilotChat(object):
    def __init__(self, cluster_conf, service_conf, default_service_conf):
        self.cluster_conf = cluster_conf
        self.service_conf = dict(default_service_conf, **service_conf)

    def get_master_ip(self):
        for host_conf in self.cluster_conf["machine-list"]:
            if "pai-master" in host_conf and host_conf["pai-master"] == "true":
                return host_conf["hostip"]
        return None

    def validation_pre(self):
        for k in ["agent-port", "secure-port", "history-depth", "agent-mode", "agent-mode-ca", "azure-openai-api-key", "llm-endpoint", "llm-model", "llm-version"]:
            if k not in self.service_conf:
                return False, f"{k} is not found in copilot-chat service configuration"
        if not self.get_master_ip():
            return False, f"No master ip found"
        return True, None

    def run(self):
        config = copy.deepcopy(self.service_conf)
        config['ip'] = self.get_master_ip()
        config['url'] = f"http://{config['ip']}:{config['agent-port']}"
        return config

    def validation_post(self, conf):
        return True, None
