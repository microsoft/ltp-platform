// Copyright (c) Microsoft Corporation
// All rights reserved.
//
// MIT License
//
// Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
// documentation files (the "Software"), to deal in the Software without restriction, including without limitation
// the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
// to permit persons to whom the Software is furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
// BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
// DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

const k8s = require('@kubernetes/client-node');
const logger = require('@alert-handler/common/logger');

const kc = new k8s.KubeConfig();

kc.loadFromDefault();

// clean finished reboot pods created by alert-handler
const cleanFinishedRebootPods = () => {
  logger.info('Cleaning finished rebooting pods...');

  const k8sApi = kc.makeApiClient(k8s.CoreV1Api);

  k8sApi.listNamespacedPod({namespace: 'default'}).then((res) => {
    const pods = res.items;
    const rebootPods = pods.filter(pod => pod.metadata.name.includes('node-rebooter') && pod.status.containerStatuses.some(status => status.state.terminated && status.state.terminated.reason === 'ContainerStatusUnknown'));
    if (rebootPods.length > 0) {
      logger.info(`Rebooting pods to be cleaned: ${rebootPods.map(pod => pod.metadata.name).join(', ')}`);
    } else {
      logger.info('No rebooting pods to be cleaned.');
    }
    rebootPods.forEach(pod => {
      k8sApi.deleteNamespacedPod({name: pod.metadata.name, namesapce: 'default'}).then(() => {
        logger.info(`Successfully deleted rebooting pod ${pod.metadata.name}`);
      }).catch((err) => {
        logger.error(`Failed to delete rebooting pod ${pod.metadata.name}: ${err}`);
      });
    });
  }).catch((err) => {
    logger.error(`Error listing rebooting pods: ${err}`);
  });
};

// module exports
module.exports = {
  cleanFinishedRebootPods,
};
