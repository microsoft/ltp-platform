# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import os
import sys
import unittest
import base

sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../src"))
import amd

class TestAmd(base.TestBase):
    def test_parse_rocm_smi_result(self):
        sample_path = "data/rocm_smi.json"
        with open(sample_path, "r") as f:
            rocm_smi_result = f.read()
        rocm_smi_parse_result = amd.parse_smi_json_result(rocm_smi_result)
        expect = [{
            "pci_addr": "0002:00:00.0",
            "temperature": 45,
            "gpu_util": 92.0,
            "gpu_mem_util": 1.6171980203827634
        }, {
            "pci_addr": "0003:00:00.0",
            "temperature": 38,
            "gpu_util": 0.0,
            "gpu_mem_util": 0.14429063609422182
        }, {
            "pci_addr": "0004:00:00.0",
            "temperature": 35,
            "gpu_util": 0.0,
            "gpu_mem_util": 0.14429063609422182
        }, {
            "pci_addr": "0005:00:00.0",
            "temperature": 37,
            "gpu_util": 0.0,
            "gpu_mem_util": 0.14429063609422182
        }, {
            "pci_addr": "0006:00:00.0",
            "temperature": 38,
            "gpu_util": 0.0,
            "gpu_mem_util": 0.14429063609422182
        }, {
            "pci_addr": "0007:00:00.0",
            "temperature": 38,
            "gpu_util": 0.0,
            "gpu_mem_util": 0.14429063609422182
        }, {
            "pci_addr": "0008:00:00.0",
            "temperature": 36,
            "gpu_util": 0.0,
            "gpu_mem_util": 0.14429063609422182
        },{
            "pci_addr": "0009:00:00.0",
            "temperature": 35,
            "gpu_util": 0.0,
            "gpu_mem_util": 0.14429063609422182
        }]
        for e, v in zip(expect, rocm_smi_parse_result.values()):
            self.assertEqual(e["pci_addr"], v.pci_addr)
            self.assertEqual(e["temperature"], v.temperature)
            self.assertEqual(e["gpu_util"], v.gpu_util)
            self.assertEqual(e["gpu_mem_util"], v.gpu_mem_util)


if __name__ == '__main__':
    unittest.main()
