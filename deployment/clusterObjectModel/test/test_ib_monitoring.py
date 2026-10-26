# Copyright (c) Microsoft Corporation
# All rights reserved.
#
# MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
# to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
# BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os
import unittest

import yaml

from ..mainParser.layout import Layout
from ...paiLibrary.common import template_handler


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))


class TestIbMonitoring(unittest.TestCase):

    def layout(self, opt_in=None):
        worker = {
            'hostname': 'worker',
            'hostip': '10.0.0.2',
            'machine-type': 'gpu',
            'pai-worker': 'true',
        }
        if opt_in is not None:
            worker['pai-ib'] = opt_in
        return {
            'machine-sku': {'gpu': {'computing-device': {'type': 'nvidia.com/gpu'}}},
            'machine-list': [
                {'hostname': 'master', 'hostip': '10.0.0.1', 'pai-master': 'true'},
                worker,
            ],
        }

    def render(self, path, cluster_cfg):
        with open(os.path.join(ROOT, path)) as template:
            return template_handler.generate_from_template_dict(
                template.read(), {'cluster_cfg': cluster_cfg})

    def test_node_opt_in_label_is_reconciled_from_layout(self):
        for opt_in in (None, 'false', 'true'):
            with self.subTest(opt_in=opt_in):
                parser = Layout(self.layout(opt_in))
                self.assertEqual(parser.validation_pre(), (True, None))
                model = parser.run()
                if opt_in is not None:
                    self.assertEqual(model['machine-list']['worker']['pai-ib'], opt_in)
                script = self.render(
                    'src/cluster-configuration/deploy/start.sh.template',
                    {'layout': model, 'cluster': {'docker-registry': {'secret-name': ''}}})
                if opt_in == 'true':
                    self.assertIn('nodes worker pai-ib=true', script)
                    self.assertNotIn('nodes worker pai-ib-', script)
                else:
                    self.assertIn('nodes worker pai-ib-', script)
                    self.assertNotIn('nodes worker pai-ib=true', script)
                self.assertIn('nodes worker vendor=nvidia', script)
                self.assertIn('nodes master pai-ib-', script)

    def test_invalid_opt_in_is_rejected(self):
        for opt_in in (None, True, False, 'yes', '', 1):
            with self.subTest(opt_in=opt_in):
                layout = self.layout()
                layout['machine-list'][1]['pai-ib'] = opt_in
                valid, error = Layout(layout).validation_pre()
                self.assertFalse(valid)
                self.assertIn('pai-ib', error)
                self.assertIn('worker', error)

    def test_prometheus_node_metadata_and_scoped_rules(self):
        for rbac in ('true', 'false'):
            for remote_write in (None, {'cluster_label': 'test', 'local_url': ''}):
                with self.subTest(rbac=rbac, remote_write=bool(remote_write)):
                    manifest = yaml.safe_load(self.render(
                        'src/prometheus/deploy/prometheus-configmap.yaml.template',
                        {
                            'cluster': {'common': {'k8s-rbac': rbac}},
                            'layout': {'kubernetes': {'api-servers-url': 'http://127.0.0.1:8000'}},
                            'alert-manager': {'host': '127.0.0.1', 'port': 9093},
                            'prometheus': {'scrape_interval': 30, 'remote_write': remote_write},
                        }))
                    config = yaml.safe_load(manifest['data']['prometheus.yml'])
                    scrape = config['scrape_configs'][0]
                    self.assertEqual(
                        scrape['kubernetes_sd_configs'][0]['attach_metadata'], {'node': True})
                    rules = scrape['relabel_configs']
                    ib_rules = [
                        rule for rule in rules
                        if isinstance(rule.get('regex'), str)
                        and rule['regex'].startswith('job-exporter;moneo-net-exporter;')
                    ]
                    self.assertEqual([rule['action'] for rule in ib_rules],
                                     ['replace', 'replace', 'drop'])
                    self.assertEqual(ib_rules[0]['regex'],
                                     'job-exporter;moneo-net-exporter;(amd|nvidia)')
                    self.assertEqual(ib_rules[1]['source_labels'][-1],
                                     '__meta_kubernetes_node_label_pai_ib')
                    self.assertEqual(ib_rules[2]['regex'],
                                     'job-exporter;moneo-net-exporter;')
