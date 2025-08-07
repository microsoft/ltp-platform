#!/usr/bin/env python3

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


import copy


class DashboardDataBackup(object):
    def __init__(self, cluster_conf, service_conf, default_service_conf):
        self.cluster_conf = cluster_conf
        self.service_conf = dict(default_service_conf, **service_conf)

    def validation_pre(self):
        for k in ["configured", "kusto-user-assigned-client-id"]:
            if k not in self.service_conf:
                return False, f"{k} is not found in dashboard data backup service configuration"
        return True, None

    def run(self):
        config = copy.deepcopy(self.service_conf)
        return config

    def validation_post(self, conf):
        return True, None
