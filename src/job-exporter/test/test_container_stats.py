# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import os
import sys
import unittest

import base

sys.path.append(os.path.abspath("../src/"))

from container_stats import parse_crictl_stats, convert_to_byte, parse_usage_limit, parse_io, parse_percentile

PACKAGE_DIRECTORY_COM = os.path.dirname(os.path.abspath(__file__))

class TestDockerStats(base.TestBase):
    """
    Test docker_stats.py
    """
    def test_parse_docker_inspect(self):
        sample_path = "data/crictl_stats_sample.txt"
        with open(sample_path, "r") as f:
            crictl_stats = f.read()

        stats_info = parse_crictl_stats(crictl_stats)
        target_stats_info = {
            '2e5eaefe441a6': {'id': '2e5eaefe441a6', 'name': 'node-exporter', 'CPUPerc': 0.0, 'MemUsageByte': 15220000.0, 'DiskUsageByte': 40960.0, 'Inodes': 13},
            'f72ca913776e1': {'id': 'f72ca913776e1', 'name': 'prometheus', 'CPUPerc': 0.02, 'MemUsageByte': 77790000.0, 'DiskUsageByte': 40960.0, 'Inodes': 13},
        }
        self.assertEqual(target_stats_info, stats_info)

    def test_convert_to_byte(self):
        self.assertEqual(380.4 * 2 ** 20, convert_to_byte("380.4MiB"))
        self.assertEqual(380.4 * 2 ** 20, convert_to_byte("380.4mib"))
        self.assertEqual(380.4 * 10 ** 6, convert_to_byte("380.4MB"))

    def test_parse_usage_limit(self):
        data = "380.4MiB / 55.03GiB"
        result = parse_usage_limit(data)
        target = {'usage': 380.4 * 2 ** 20, 'limit': 55.03 * 2 ** 30}
        self.assertEqual(target, result)

    def test_parse_io(self):
        data = "0B / 0B"
        result = parse_io(data)
        target = {'out': 0.0, 'in': 0.0}
        self.assertEqual(target, result)

    def test_parse_percentile(self):
        data = "24.45%"
        result = parse_percentile(data)
        target = 24.45
        self.assertEqual(target, result)

if __name__ == '__main__':
    unittest.main()
