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
            "pci_addr": "0000:0C:00.0",
            "temperature": 50
        }, {
            "pci_addr": "0000:22:00.0",
            "temperature": 52
        }, {
            "pci_addr": "0000:38:00.0",
            "temperature": 49
        }, {
            "pci_addr": "0000:5C:00.0",
            "temperature": 47
        }, {
            "pci_addr": "0000:9F:00.0",
            "temperature": 48
        }, {
            "pci_addr": "0000:AF:00.0",
            "temperature": 49
        }, {
            "pci_addr": "0000:BF:00.0",
            "temperature": 46
        },{
            "pci_addr": "0000:DF:00.0",
            "temperature": 50
        }]
        for e, v in zip(expect, rocm_smi_parse_result.values()):
            self.assertEqual(e["pci_addr"], v.pci_addr)
            self.assertEqual(e["temperature"], v.temperature)


if __name__ == '__main__':
    unittest.main()
