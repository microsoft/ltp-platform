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
const kc = new k8s.KubeConfig();
const logger = require('@alert-handler/common/logger');
const crypto = require('crypto');

kc.loadFromDefault();

async function SyncUserLogs(nodeName) {
  try {
    const k8sApi = kc.makeApiClient(k8s.CoreV1Api);
    const allPods = await k8sApi.listPodForAllNamespaces();
    // Find the log-manager pod running on the specified node
    const logManagerPod = allPods.body.items.find(pod =>
      pod.metadata.namespace === 'default' &&
      pod.spec.nodeName === nodeName &&
      pod.metadata.name.includes('log-manager')
    );
    if (!logManagerPod) {
      logger.info(`No log-manager pod found on the specified node ${nodeName}.`);
      return false;
    }
    const namespace = logManagerPod.metadata.namespace;
    const podName = logManagerPod.metadata.name;
    const containerName = 'log-cleaner';

    const exec = new k8s.Exec(kc);
    try {
      await exec.exec(
        namespace,
        podName,
        containerName,
        ['bash', '-c', '/etc/periodic/daily/rsync_logs'],
        process.stdout,
        process.stderr,
        process.stdin,
        true
      );
      logger.info(`Command executed successfully in ${podName} ${containerName} ${nodeName}`);
      return true;
    } catch (error) {
      logger.error(`Error executing command in pod: ${error.message}`);
      return false;
    }
  } catch (error) {
    logger.error(`Error fetching pods: ${error.message}`);
    return false;
  }
}

// Retry logic for SyncUserLogs
const retrySyncUserLogs = async (nodeName, retries) => {
  let attempts = 0;
  while (attempts < retries) {
    let result = await SyncUserLogs(nodeName);
    if (result) {
      return;
    }
    else {
      attempts++;
      logger.log(`SyncUserLogs failed. Attempt ${attempts} of ${retries}`);
      if (attempts >= retries) {
        logger.error("Failed to sync user logs after retries.");
        return
      }
      // Wait before retrying
      await new Promise((resolve) => setTimeout(resolve, 1000)); // Wait 1 seconds before retrying
    }
  }
};

const cordonNode = async (nodeName) => {
  const headers = {
    'content-type': 'application/strategic-merge-patch+json',
  };
  // Set the node unschedulable
  const k8sApi = kc.makeApiClient(k8s.CoreV1Api);
  const patchNodePromise = k8sApi.patchNode(
    nodeName,
    { spec: { unschedulable: true } },
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    { headers },
  );

  const syncLogsPromise = retrySyncUserLogs(nodeName, 2);

  // Return both promises in parallel
  return Promise.all([patchNodePromise, syncLogsPromise])
    .then(([patchResponse, syncResponse]) => {
      return patchResponse; // Return the patch response
    })
    .catch((error) => {
      console.error(`Error while cordoning node ${nodeName}: ${error.message}`);
      throw new Error(`Failed to cordon node ${nodeName}`);
    });
};

const uncordonNode = async (nodeName) => {
  const headers = {
    'content-type': 'application/strategic-merge-patch+json',
  };
  // set the node unschedulable
  const k8sApi = kc.makeApiClient(k8s.CoreV1Api);
  return k8sApi.patchNode(
    nodeName,
    { spec: { unschedulable: false } },
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    { headers },
  );
}

const cordonNodes = (req, res) => {
  logger.info(
    'alert-handler received `cordonNode` post request from alert-manager.',
  );

  // extract nodes to cordon
  const nodeNames = [...new Set(
    req.body.alerts
      .filter((alert) => alert.status === 'firing' && 'node_name' in alert.labels)
      .map((alert) => alert.labels.node_name)
  )];

  if (nodeNames.length === 0) {
    return res.status(200).json({
      message: 'No nodes to cordon.',
    });
  }
  logger.info(`alert-handler will cordon these nodes: ${nodeNames}`);

  // cordon all these nodes
  Promise.all(nodeNames.map((nodeName) => cordonNode(nodeName)))
    .then((response) => {
      logger.info(`alert-handler successfully cordon nodes: ${nodeNames}`);
      res.status(200).json({
        message: `alert-handler successfully cordon nodes`,
      });
    })
    .catch((error) => {
      logger.error(error.message);
      res.status(500).json({
        message: `alert-handler failed to cordon node`,
      });
    });
};

const uncordonNodes = (req, res) => {
  logger.info(
    'alert-handler received `uncordonNode` post request from alert-manager.',
  );

  // extract nodes to uncordon
  const nodeNames = [...new Set(
    req.body.alerts
      .filter((alert) => alert.status === 'firing' && 'node_name' in alert.labels)
      .map((alert) => alert.labels.node_name)
  )];

  if (nodeNames.length === 0) {
    return res.status(200).json({
      message: 'No nodes to uncordon.',
    });
  }
  logger.info(`alert-handler will uncordon these nodes: ${nodeNames}`);

  // cordon all these nodes
  Promise.all(nodeNames.map((nodeName) => uncordonNode(nodeName)))
    .then((response) => {
      logger.info(`alert-handler successfully uncordon nodes: ${nodeNames}`);
      res.status(200).json({
        message: `alert-handler successfully uncordon nodes`,
      });
    })
    .catch((error) => {
      logger.error(errorl.message);
      res.status(500).json({
        message: `alert-handler failed to uncordon node`,
      });
    });
};

const drainNode = async (nodeName) => {
  logger.info(`Draining node: ${nodeName}`);
  const k8sApi = kc.makeApiClient(k8s.CoreV1Api);

  try {
    // Get all pods on the node (excluding DaemonSets)
    const allPods = await k8sApi.listPodForAllNamespaces();
    const podNames = allPods.body.items.filter(
      pod => pod.metadata.namespace === 'default' && pod.spec.nodeName === nodeName && !pod.metadata.ownerReferences?.some(ref => ref.kind === 'DaemonSet'))
      .map(pod => pod.metadata.name);

    if (podNames.length === 0) {
      logger.info(`No non-DaemonSet pods to evict on ${nodeName}.`);
      return;
    }

    // Evict each pod
    await Promise.all(
      podNames.map(podName =>
        k8sApi.deleteNamespacedPod(podName, 'default')
      )
    );

    logger.info(`Successfully drained node: ${nodeName}`);
  } catch (error) {
    logger.error(`Failed to drain node ${nodeName}: ${error.message}`);
    throw error;
  }
};


const getRebootPod = (nodeName) => ({
  apiVersion: "v1",
  kind: "Pod",
  metadata: {
    name: `node-rebooter-${crypto.createHash('md5').update(nodeName).digest('hex').slice(0, 10)}`, // Shortened for safety
    namespace: "default",
    labels: { "created-by": "alert-handler" },
  },
  spec: {
    tolerations: [{ key: "node.kubernetes.io/unschedulable", operator: "Exists" }],
    hostPID: true,
    nodeSelector: { "kubernetes.io/hostname": nodeName },
    containers: [{
      name: "rebooter",
      image: "busybox",
      command: ["sh", "-c", "sleep 5; sync; reboot -f"], // Ensures sync before force reboot
      securityContext: { privileged: true },
    }],
    restartPolicy: "Never",
  },
});

const checkNodeCordoned = async (nodeName) => {
  const k8sApi = kc.makeApiClient(k8s.CoreV1Api);
  // Check if the node is already cordoned
  const { body: node } = await k8sApi.readNode(nodeName);
  const isCordoned = node.spec.unschedulable === true;
  if (isCordoned) {
    return true;
  }
  return false;
};

const drainNodes = async (req, res) => {
  logger.info('alert-handler received `drainNode` post request from alert-manager.');
  const nodeNames = req.body.alerts
    .filter(alert => alert.status === 'firing' && 'node_name' in alert.labels)
    .map(alert => alert.labels.node_name);

  if (nodeNames.length === 0) {
    return res.status(200).json({ message: 'No nodes to reboot.' });
  }
  logger.info(`alert-handler will drain these nodes: ${nodeNames}`);

  const results = await Promise.allSettled(nodeNames.map(async (nodeName) => {
    try {
      if (await checkNodeCordoned(nodeName)) {
        logger.info(`Node ${nodeName} is already cordoned. Skipping drain.`);
        await cordonNode(nodeName);
        return { nodeName, status: 'fulfilled' };
      }
      await cordonNode(nodeName);
      await drainNode(nodeName);
      logger.info(`Successfully triggered drain for node: ${nodeName}`);
      return { nodeName, status: 'fulfilled' };
    } catch (error) {
      logger.error(`Failed to trigger drain for node ${nodeName}: ${error.message}`);
      return { nodeName, status: 'rejected', reason: error.message };
    }
  }));

  const failedNodes = results.filter(result => result.status === 'rejected').map(result => result.nodeName);
  if (failedNodes.length > 0) {
    res.status(500).json({ message: `Failed to trigger drain for nodes: ${failedNodes.join(', ')}` });
  } else {
    res.status(200).json({ message: `Successfully triggered drain for all nodes` });
  }
};

const rebootNodes = async (req, res) => {
  logger.info('alert-handler received `rebootNode` post request from alert-manager.');
  const nodeNames = req.body.alerts
    .filter(alert => alert.status === 'firing' && 'node_name' in alert.labels)
    .map(alert => alert.labels.node_name);

  if (nodeNames.length === 0) {
    return res.status(200).json({ message: 'No nodes to reboot.' });
  }
  logger.info(`alert-handler will reboot these nodes: ${nodeNames}`);

  const results = await Promise.allSettled(nodeNames.map(async (nodeName) => {
    try {
      await cordonNode(nodeName);
      await drainNode(nodeName);
      const k8sApi = kc.makeApiClient(k8s.CoreV1Api);
      await k8sApi.createNamespacedPod("default", getRebootPod(nodeName));
      logger.info(`Successfully triggered reboot for node: ${nodeName}`);
      return { nodeName, status: 'fulfilled' };
    } catch (error) {
      logger.error(`Failed to trigger reboot for node ${nodeName}: ${error.message}`);
      return { nodeName, status: 'rejected', reason: error.message };
    }
  }));

  const failedNodes = results.filter(result => result.status === 'rejected').map(result => result.nodeName);
  if (failedNodes.length > 0) {
    res.status(500).json({ message: `Failed to trigger reboot for nodes: ${failedNodes.join(', ')}` });
  } else {
    res.status(200).json({ message: `Successfully triggered reboot for all nodes` });
  }
};

const getK8sV1Job = (jobName, nodeName, minorNumber) => {
  const DOCKER_REGISTRY_PREFIX = process.env.DOCKER_REGISTRY_PREFIX;
  const DOCKER_REGISTRY_TAG = process.env.DOCKER_REGISTRY_TAG;
  const job = {
    apiVersion: 'batch/v1',
    kind: 'Job',
    metadata: {
      name: jobName,
      labels: {
        'created-by': 'alert-handler',
        'time-to-live': '24h',
      },
    },
    spec: {
      // TTL feature is currently alpha[Kubernetes 1.15]
      // To avoid using this fearure, jobs with label `time-to-live=24h` & `created-by=alert-handler` will be cleaned with function `cleanTTL24HJobs` regularlly
      // ttlSecondsAfterFinished: 86400,
      template: {
        spec: {
          containers: [
            {
              name: 'nvidia-gpu-low-perf-fixer',
              image: `${DOCKER_REGISTRY_PREFIX}nvidia-gpu-low-perf-fixer:${DOCKER_REGISTRY_TAG}`,
              imagePullPolicy: 'Always',
              env: [
                {
                  name: 'MINOR_NUMBER',
                  value: `${minorNumber}`,
                },
              ],
              securityContext: {
                privileged: true,
              },
            },
          ],
          restartPolicy: 'Never',
          nodeSelector: {
            'kubernetes.io/hostname': nodeName,
          },
        },
      },
    },
  };
  return job;
};

// start a k8s job for each GPU card to fix NvidiaGPULowPerf issue
const fixNvidiaGPULowPerf = (req, res) => {
  logger.info(
    'Received `fixNvidiaGPULowPerf` post request from alert-manager.',
  );
  // filter alerts which are firing and contain `node_name` & `minor_number` as label
  const jobsInfo = req.body.alerts
    .filter(
      (alert) =>
        alert.status === 'firing' &&
        'node_name' in alert.labels &&
        'minor_number' in alert.labels,
    )
    // map each alert to a job
    .map((alert) => ({
      jobName: `nvidia-gpu-low-perf-fixer-${crypto
        .createHash('md5')
        .update(alert.labels.node_name + alert.labels.minor_number)
        .digest('hex')}`, // unique job by GPU card
      nodeName: alert.labels.node_name,
      minorNumber: alert.labels.minor_number,
      DOCKER_REGISTRY_PREFIX: process.env.DOCKER_REGISTRY_PREFIX,
      DOCKER_REGISTRY_TAG: process.env.DOCKER_REGISTRY_TAG,
    }));

  const k8sApi = kc.makeApiClient(k8s.BatchV1Api);
  jobsInfo.forEach(async (jobInfo) => {
    // get k8s V1Job
    const job = getK8sV1Job(
      jobInfo.jobName,
      jobInfo.nodeName,
      jobInfo.minorNumber,
    );
    k8sApi
      .createNamespacedJob('default', job)
      .then((response) => {
        logger.info(
          `Successfully start job ${jobInfo.jobName} for GPU Low Performance issue in node: ${jobInfo.nodeName}, minor number: ${jobInfo.minorNumber}`,
        );
      })
      .catch((error) => {
        // ignore the job creation if already exists
        if (error.response && error.response.statusCode === 409) {
          logger.warn(`Kubernetes job ${jobInfo.jobName} already exists.`);
        } else {
          logger.error(error.message);
          res.status(500).json({
            message: `Failed to start job to fix NvidiaGPULowPerf`,
          });
        }
      });
  });
};

// module exports
module.exports = {
  cordonNodes,
  fixNvidiaGPULowPerf,
  drainNodes,
  rebootNodes,
  uncordonNodes,
};
