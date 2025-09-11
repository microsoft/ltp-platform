# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import copy

class ModelProxy(object):
    def __init__(self, cluster_conf, service_conf, default_service_conf):
        self.cluster_conf = cluster_conf
        self.service_conf = service_conf
        self.default_service_conf = default_service_conf

    def get_master_ip(self):
        for host_conf in self.cluster_conf["machine-list"]:
            if "pai-master" in host_conf and host_conf["pai-master"] == "true":
                return host_conf["hostip"]

    def validation_pre(self):
        return True, None

    def run(self):
        result = copy.deepcopy(self.default_service_conf)
        result.update(self.service_conf)
        result["host"] = self.get_master_ip()
        result["url"] = "http://{0}:{1}".format(self.get_master_ip(), result["port"])
        return result

    def validation_post(self, conf):
        port = conf["model-proxy"].get("port")
        if type(port) != int:
            msg = "expect port in model-proxy to be int but get %s with type %s" % \
                    (port, type(port))
            return False, msg
        return True, None
