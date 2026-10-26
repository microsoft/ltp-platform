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
import shutil
import sys
import tempfile
import unittest
import yaml
import logging
import logging.config

from ...paiLibrary.common import directory_handler
from ...paiLibrary.common import file_handler
from ...clusterObjectModel.cluster_object_model import cluster_object_model
from ...paiLibrary.paiService.service_template_generate import service_template_generate
from ...paiLibrary.paiService.service_template_clean import  service_template_clean


package_directory_com = os.path.dirname(os.path.abspath(__file__))


class TestTemplateGenerate(unittest.TestCase):

    def setUp(self):

        try:

            os.chdir(package_directory_com)

        except:

            pass

        configuration_path = "data/test_logging.yaml"

        if os.path.exists(configuration_path):
            with open(configuration_path, 'rt') as f:
                logging_configuration = yaml.safe_load(f.read())

            logging.config.dictConfig(logging_configuration)

            logging.getLogger()



    def test_template_generate(self):

        com_handler = cluster_object_model("{0}/data/configuration-template-generate".format(package_directory_com))
        com = com_handler.service_config()
        src_path = "{0}/../../../src".format(package_directory_com)

        service_list = list()

        subdir_list = directory_handler.get_subdirectory_list(src_path)
        for subdir in subdir_list:
            service_deploy_dir = "{0}/{1}/deploy".format(src_path, subdir)
            service_deploy_conf_path = "{0}/{1}/deploy/service.yaml".format(src_path, subdir)
            if file_handler.directory_exits(service_deploy_dir) and file_handler.file_exist_or_not(service_deploy_conf_path):
                service_conf = file_handler.load_yaml_config(service_deploy_conf_path)
                if ("cluster-type" not in service_conf) or ("cluster-type" in service_conf and "k8s" in service_conf["cluster-type"]):
                    service_list.append(subdir)

        for serv in service_list:
            service_conf = file_handler.load_yaml_config("{0}/{1}/deploy/service.yaml".format(src_path, serv))
            service_template_generater = service_template_generate(com, serv, service_conf)
            service_template_generater.run()
            service_template_cleaner = service_template_clean(serv, service_conf)
            service_template_cleaner.run()


class TestPaiNodePlacement(unittest.TestCase):

    def render_service(self, service, optional_features=False):
        cluster_cfg = {
            'cluster': {
                'common': {
                    'cluster-type': 'k8s',
                    'qos-switch': 'true' if optional_features else 'false',
                },
                'docker-registry': {
                    'prefix': 'example.invalid/pai/',
                    'tag': 'test',
                    'secret-name': 'pull-secret' if optional_features else '',
                },
            },
            'prometheus': {'scrape_interval': 30},
            'job-exporter': {
                'job-port': 9102,
                'gpu-port': 8000,
                'net-port': 8001,
                'node-port': 8002,
                'logging-level': 'INFO',
                'net_exporter_interval': 10,
            },
            'log-manager': {
                'port': 9103,
                'remote_storage_pvc': 'log-pvc' if optional_features else '',
                'admin_name': 'test-admin',
                'admin_password': 'test-only-password',
                'jwt_secret': 'test-only-secret',
                'token_expired_second': 3600,
            },
            'node-exporter': {'port': 9100},
        }
        src = os.path.abspath(os.path.join(package_directory_com, '../../../src'))
        deploy_dir = os.path.join(src, service, 'deploy')
        service_conf = file_handler.load_yaml_config(os.path.join(deploy_dir, 'service.yaml'))
        with tempfile.TemporaryDirectory() as temporary_src:
            target_dir = os.path.join(temporary_src, service, 'deploy')
            os.makedirs(target_dir)
            for output in service_conf['template-list']:
                shutil.copyfile(
                    os.path.join(deploy_dir, output + '.template'),
                    os.path.join(target_dir, output + '.template'))
            generator = service_template_generate(cluster_cfg, service, service_conf)
            generator.src_path = temporary_src
            generator.run()
            with open(os.path.join(target_dir, service + '.yaml')) as manifest:
                return yaml.safe_load(manifest)

    def test_master_or_worker_with_service_opt_out(self):
        for service, excluded_label in (
                ('job-exporter', 'no-jobexporter'),
                ('log-manager', 'no-logmanager')):
            for optional_features in (False, True):
                with self.subTest(service=service, optional_features=optional_features):
                    manifest = self.render_service(service, optional_features)
                    affinity = manifest['spec']['template']['spec']['affinity']['nodeAffinity']
                    self.assertEqual(
                        affinity['requiredDuringSchedulingIgnoredDuringExecution']['nodeSelectorTerms'],
                        [
                            {'matchExpressions': [
                                {'key': role, 'operator': 'In', 'values': ['true']},
                                {'key': excluded_label, 'operator': 'NotIn', 'values': ['true']},
                            ]}
                            for role in ('pai-master', 'pai-worker')
                        ])

    def test_node_exporter_remains_available_on_system_nodes(self):
        manifest = self.render_service('node-exporter')
        affinity = manifest['spec']['template']['spec']['affinity']['nodeAffinity']
        self.assertEqual(
            affinity['requiredDuringSchedulingIgnoredDuringExecution']['nodeSelectorTerms'],
            [{'matchExpressions': [
                {'key': 'no-nodeexporter', 'operator': 'NotIn', 'values': ['true']},
            ]}])
