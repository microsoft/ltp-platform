#!/usr/bin/env python

import copy

class SshProxy(object):
    def __init__(self, cluster_conf, service_conf, default_service_conf):
        self.cluster_conf = cluster_conf
        self.service_conf = service_conf
        self.default_service_conf = default_service_conf

    def get_master_ip(self):
        for host_conf in self.cluster_conf["machine-list"]:
            if "pai-master" in host_conf and host_conf["pai-master"] == "true":
                return host_conf["hostip"]

    def validation_pre(self):
        for k in ["public-key"]:
            if k not in self.service_conf:
                return False, f"{k} is not found in ssh-proxy service configuration"
        if not self.get_master_ip():
            return False, f"No master ip found"
        return True, None

    def run(self):
        result = copy.deepcopy(self.default_service_conf)
        result.update(self.service_conf)
        return result

    def validation_post(self, conf):
        return True, None
