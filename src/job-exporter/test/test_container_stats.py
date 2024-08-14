# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import os
import sys
import unittest

import base

sys.path.append(os.path.abspath("../src/"))

from container_stats import parse_nerdctl_stats, convert_to_byte, parse_usage_limit, parse_io, parse_percentile

PACKAGE_DIRECTORY_COM = os.path.dirname(os.path.abspath(__file__))

class TestDockerStats(base.TestBase):
    """
    Test docker_stats.py
    """
    def test_parse_docker_inspect(self):
        sample_path = "data/nerdctl_stats_sample.jsonl"
        with open(sample_path, "r") as f:
            nerdctl_stats = f.read()

        stats_info = parse_nerdctl_stats(nerdctl_stats)
        target_stats_info = {
            '36c48a34101a769608358410b9d47a1b6569fa077a8d56cfd42927b5da003fed': {'id': '36c48a34101a769608358410b9d47a1b6569fa077a8d56cfd42927b5da003fed', 'name': {'namespace': 'default', 'pod': '02cceae4ebd403b2b367e0376ecce449-worker-8', 'container': 'app'}, 'cpuPerc': 1573.05, 'memPerc': 56.23, 'memUsage': {'usage': 482969072435.2, 'limit': 858993459200.0}, 'netIO': {'in': 578000000000.0, 'out': 31500000000.0}, 'blockIO': {'in': 1180000.0, 'out': 12800000000.0}},
            '38348f12dad446032ceb67fa73ee745da3a83883643742f425019d29a2f722db': {'id': '38348f12dad446032ceb67fa73ee745da3a83883643742f425019d29a2f722db', 'name': {'namespace': 'default', 'pod': 'job-exporter-7c9mw', 'container': 'moneo-gpu-exporter'}, 'cpuPerc': 6.47, 'memPerc': 0.0, 'memUsage': {'usage': 27315404.8, 'limit': 1.8446744073709552e+19}, 'netIO': {'in': 578000000000.0, 'out': 31500000000.0}, 'blockIO': {'in': 8850000.0, 'out': 205000.0}}
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
