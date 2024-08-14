# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.


import sys
import os
import unittest
import base

sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../src"))

from container_inspect import parse_nerdctl_inspect, InspectResult
from utils import GpuVendor

class TestContainerInspect(base.TestBase):
    """
    Test container.py
    """
    # TODO: Fix the test cases
    def test_parse_container_inspect_amd(self):
        sample_path = "data/container_inspect_amd.json"
        with open(sample_path, "r") as f:
            docker_inspect = f.read()

        inspect_info = parse_nerdctl_inspect(docker_inspect, GpuVendor.AMD)
        target_inspect_info = InspectResult(
            "binyli", "binyli~admin_8fc0983c", "taskrole", "0",
            "0", "0_f3c2300b-b2d1-4c19-aca2-a889ad3fed51", "default", 2722314)
        self.assertEqual(target_inspect_info, inspect_info)

    def test_parse_container_inspect(self):
        sample_path = "data/container_inspect.json"
        with open(sample_path, "r") as f:
            container_inspect = f.read()

        inspect_info = parse_nerdctl_inspect(container_inspect, GpuVendor.NVIDIA)
        target_inspect_info = InspectResult("xiaoliu2", "xiaoliu2~GKV_Pretrain_CA_node64_v3_single", "worker", "8", "0,1,2,3,4,5,6,7", "0_8e96aa4b-160b-47f0-bd6c-d9b40406be74", "default", 3913655)
        self.assertEqual(target_inspect_info, inspect_info)


if __name__ == '__main__':
    unittest.main()
