# Copilot Chat Service Configuration

This document describes the configuration and deployment structure for the Copilot Chat service.

## Table of Contents

- [Overview](#overview)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Directory Structure](#directory-structure)
- [Troubleshooting](#troubleshooting)

## Overview

Copilot Chat is a modular, containerized service designed to provide chat-based copilot functionality. It is structured for extensibility and integration with other agents and services.

## Configuration

### Main Configuration File: `config/copilot-chat.yaml`

This YAML file defines the core configuration for the Copilot Chat service.

**Example:**
```yaml
service_type: "common"
port: 
  - 50000
  - 8443
```

- `service_type`: The type of service (default: "common").
- `port`: List of ports exposed by the service.

## Deployment

Deployment scripts are located in the `deploy/` directory:

- `start.sh`: Start the service container.
- `stop.sh`: Stop the running container.
- `refresh.sh`: Rebuild and restart the service.
- `set.sh`: Set environment variables for deployment.

**Example:**
```bash
cd deploy/
./start.sh
```

## Directory Structure

- `build/`: Dockerfiles and build scripts for containerization.
- `config/`: Service configuration files (YAML).
- `deploy/`: Deployment and management scripts.
- `src/`: Source code, agents, and supporting libraries.
  - `agents/`: Agent implementations (e.g., lucia-slt-copilot-agent).
  - `sdks/

## Sample Questions

Date: 2025-07-30 (with LTP V1.2 release)

### Performance Status

#### Evaluation Method

The evaluation process is based on human-labeled ground truth for all questions. For each category, we assess performance using the following metrics:

- **Accuracy**: Calculated as the ratio of correctly handled items to the total number of items for each step:
  - Classification (exact match)
  - Query Generation (TBD)
  - Answer Generation (semantic match)
- **Mean Duration**: The average time taken to answer a question within each category.
- **Max Duration**: The longest time taken to answer a question within each category.

These metrics provide a comprehensive view of both correctness and efficiency across all evaluation steps.

#### Results

| Category             | Count | Support Level    | Classification Accuracy | Query Generation Accuracy | Answer Generation Accuracy | Mean Duration (s) | Max Duration (s) | Words per Second |
|----------------------|-------|------------------|-------------------------|---------------------------|----------------------------|-------------------|------------------|------------------|
| Human Intervention   | 17    | Full             | 0.76                    | NA                        | TBD                        | 13.83             | 17.74            | 8.33             |
| User Manual          | 28    | Full             | 0.96                    | NA                        | TBD                        | 13.72             | 23.73            | 21.00            |
| Auto Rejection       | 3     | Full             | 1                       | NA                        | TBD                        | 8.84              | 10.70            | 13.15            |
| Cluster Job Metrics  | 19    | Not supported    | (0.89)                  | TBD                       | TBD                        | (16.34)           | (26.95)          | (12.42)          |
| Job Metadata         | 1     | Full             | 1                       | TBD                       | TBD                        | 19.91             | 19.91            | 13.25            |
| Dashboard            | 30    | Limited, Cached  | 0.97                    | TBD                       | TBD                        | 13.08             | 18.70            | 11.77            |

### Questions to Tryout

#### Human Intervention

These questions require manual intervention or troubleshooting by administrators or support teams. They often involve issues like node failures, network problems, or errors when interacting with the web portal, such as job submission errors.

| id | question | solution
| --- | --- | --- |
| 1750824932541 | Hi Admin,I have been trying to get 4 nodes and successfully been allocated. However, it gets stuck three nodes are running and one keeps waiting -- blocking the whole process. Can you please take a look at it? Job config is here | human_intervention |
| 1748494435547 | Hi LTP admins,seems that we meet some network issue today, some nodes can connect to archive.ubuntu.com but some cannot, could you help to check?Err:12 http://archive.ubuntu.com/ubuntu jammy InRelease  Could not connect to archive.ubuntu.com:80 (185.125.190.81), connection timed out Could not connect to archive.ubuntu.com:80 (91.189.91.82), connection timed out Could not connect to archive.ubuntu.com:80 (185.125.190.83), connection timed out Could not connect to archive.ubuntu.com:80 (185.125.190.82), connection timed out Could not connect to archive.ubuntu.com:80 (91.189.91.83), connection timed outErr:13 http://archive.ubuntu.com/ubuntu jammy-updates InRelease  Unable to connect to archive.ubuntu.com:80:Err:14 http://archive.ubuntu.com/ubuntu jammy-backports InRelease  Unable to connect to archive.ubuntu.com:80:Fetched 8925 kB in 38s (232 kB/s)Reading package lists...Reading package lists...Building dependency tree...Reading state information... | human_intervention |
| 1746675314245 | Hi LTP admins,We meet this issue, seems the portal is crashed. | human_intervention |
| 1746765398938 | Hi admins,We have a 16 node job failed and we have try to resume several times, each time failed seems because of communication, could you help to find if there are some bad nodes in it?These are job links:LTP, LTP | human_intervention |
| 1746855813188 | Hi LTP admins,When I try to submit job this afternoon, the portal says ErrorCould you help to check the portal's status? many thanks  | human_intervention |
| 1746838829038 | hi, admins, we have a 16-node job that seems to be hanging during startup — the GPU utilization stays at 0. We've retried multiple times on the same 16 nodes, but the issue persists each time.Could you please help check if there might be any issues with these nodes?here is the job link https://wcu.openpai.org/job-detail.html?username=lzhani&amp;jobName=qwen-32b-ins-math-max-turn-20-no-stop-token-bsz512-n64-down-sample-26 | human_intervention |
| 1746681496761 | Hi LTP admins,Thanks to the powerful Lucia platform, we have successfully started several 16-node experiments.However, when some experiments are stopped, it seems that the portal does not show that these nodes have been released. This may also cause the jobs submitted later to be waiting all the time.running job takes 128 + 128 +64 = 320, portal shows that 448 in used.And is it possible to replace the 3 bad nodes in the cluster so that we can start an additional experiment or scale up the current experiment, which will speed up our experiment progress. | human_intervention |
| 1746668514801 | Hi Admins,It seems that there are some potentially faulty nodes on the rstar VC. When we submit multi-node jobs, they may randomly land on these problematic nodes, causing job failures—even though the codebase remains unchanged.Here are two job links that may help illustrate the issue:LTPLTPWould it be possible to detect these potentially bad nodes and report them for maintenance?Thanks for your help! | human_intervention |
| 1743257283532 | sigma-s-mi300 shows it has been fully used (100%, so no more jobs can be submitted), but just half of the GPUs and CPUs shown been occupied. See the attached screenshot. | human_intervention |
| 1741833872192 | This job encountered "No CUDA GPUs are available". Platform for AI Is the node broken? | human_intervention |
| 1741228363895 | When submitting a job through OpenPAI, the pvc-blob-fuse mount process often fails. See the configure file below. Can anyone take a look at it? Thanks.  - plugin: teamwise_storage  parameters:  storageConfigNames:  - pvc-blob-fuse  - pvc-blob-fuse-out | human_intervention |
| 1733506086099 | As far as we know, there are three ways for us to communicate with blob storage:Using storage configs pvc-blob-fuse/pvc-blob-fuse-out or pvc-blob-nfs for read and write a public blob container.Using blobfuse2 to manually mount our private blob containers for rw.Using azcopy to pre-download necessary files and post-upload results to some specific blob containers.When we are training small models like less than 2B model, the problem may not so obvious and may not cause timeout.But recently, we are trying 7B and 10B models, whose ckpt will be 110G+ (together with the sliced states of each GPU), we may need to continually start with a previously trained ckpt and save the updated ckpts periodically. This demand may require not slow IO speed with blob.We try to save a ckpt after the second step in a training experiment. The current results are:Saving 7B model with method 1 will be timeout: Platform for AISaving 7B model with method 2 is okay: Platform for AI(Method 3 require too much labour for saving ckpts periodically) | human_intervention |
| faq0000 | Why is my job always stuck in the Waiting status? | human_intervention |
| faq0001 | Why can't I see the latest VC settings on the home page? | human_intervention |
| faq0002 | Multi-Nodes throughput is very slow | human_intervention |
| iss0001 | Requesting fewer than 8 GPUs often results in unreasonably long waiting times, even when there is sufficient GPU capacity. In contrast, requesting 8 GPUs can be served immediately. | human_intervention |
| iss0006 | Multiple users have reported experiencing unreasonable waiting times even when the available GPU count is greater than the requested GPU count. | human_intervention |

#### User Manual

These questions pertain to inquiries about the features available on the Lucia Training Platform and provide instructions or explanations on how to use these features effectively.

| id | question | solution
| --- | --- | --- |
| 1746339895889 | Hi admins, I'm new to openpai, it would be nice if I could access the job via ssh for debugging, currently I can only modify the yaml file and rerun the job for debugging, which is a bit cumbersome. | user_manual |
| 1743111872398 | Is there any jump machine that can be used to ssh to the MI300x machine? | user_manual |
| iss0000 | Users may not be familiar with certain types of GPUs (especially AMD GPUs). Launching jobs on these GPUs often results in a higher failure rate due to lack of familiarity. | user_manual |
| iss0002 | The behavior of different job priorities is not transparent to users, making it difficult for them to make informed decisions. | user_manual |
| f3c2idx0 | how to submit a distributed training job? | user_manual |
| f3c2idx1 | Can I setup a SSH connection to the node? | user_manual |
| f3c2idx2 | How do I submit a "Hello World" job on the Lucia Training Platform? | user_manual |
| f3c2idx3 | What are the steps to log in and access the Lucia Training Platform for the first time? | user_manual |
| f3c2idx4 | How do I write a job configuration file for a single-node job? | user_manual |
| f3c2idx5 | What is the purpose of the task role name in the job configuration, and how do I define it? | user_manual |
| f3c2idx6 | How can I set up a distributed job configuration using multiple nodes? | user_manual |
| f3c2idx7 | How do I use a public Docker image in my job configuration? | user_manual |
| f3c2idx8 | What steps are required to use a private Docker image from Azure Container Registry (ACR)? | user_manual |
| f3c2idx9 | How do I upload and use my code from a private Git repository in a job? | user_manual |
| f3c2idx10 | What are the steps to access data from Azure Blob Storage in a job? | user_manual |
| f3c2idx11 | How can I onboard and integrate private Azure Blob Storage into the platform? | user_manual |
| f3c2idx12 | What are the different job priority types supported by the platform, and how do they work? | user_manual |
| f3c2idx13 | How can I submit a job with production priority, and what is the approval process? | user_manual |
| f3c2idx14 | How will I be notified about the status of my job (e.g., start, finish, or failure)? | user_manual |
| f3c2idx15 | What happens if my job exhibits abnormal behavior, and how will I be informed? | user_manual |
| f3c2idx16 | How do I define and use parameters and secrets in my job configuration? | user_manual |
| f3c2idx17 | How can I enable InfiniBand for distributed jobs between nodes? | user_manual |
| f3c2idx18 | What is the purpose of the SSH plugin in distributed jobs, and how do I configure it? | user_manual |
| f3c2idx19 | What should I do if my job is stuck in the "Waiting" status? | user_manual |
| f3c2idx20 | How can I debug and SSH into a running job if needed? | user_manual |
| f3c2idx21 | How can a UserGroup Admin request access to a Virtual Cluster (VC)? | user_manual |
| f3c2idx22 | What is the process for notifying users about VC assignment or re-assignment changes? | user_manual |
| f3c2idx23 | How can I report an issue or provide feedback about the Lucia Training Platform? | user_manual |

#### Auto Rejection

These questions highlight scenarios where automated systems reject requests due to features that are not supported by the platform, by design.

| id | question | solution
| --- | --- | --- |
| iss0003 | There is no mechanism to prevent Virtual Cluster (VC) resource abuse, such as requesting an excessive number of GPUs. | auto_rejection |
| iss0004 | Users may be duplicating efforts by building Docker images that have already been created by others. | auto_rejection |
| iss0005 | Users are unable to manage their expectations regarding job completion times due to a lack of visibility into job progress or estimated end times. | auto_rejection |


#### Cluster Job Metrics

These questions focus on analyzing and querying metrics related to GPU usage, job performance, and resource allocation within the cluster.

| id | question | solution
| --- | --- | --- |
| 1733587508938 | I conducted experiments using the same environment and dataset on both a single node and multiple nodes. From the experiments, I observed the following:The total training steps for a single node are 8,638, with an estimated training time of around 52 hours.Platform for AIThe total training steps for 4 nodes are 2,159, with an estimated training time of around 77 hours. Platform for AII am wondering whether there might be some communication overhead causing the training time on multiple nodes to be higher than on a single node. Thank you! | cluster_job_metrics |
| f3c1idx0 | query allocated gpu hours, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx1 | query total gpu hours, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx2 | query healthy gpu hours, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx3 | query allocated gpu hours, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx4 | query non-used gpu hours, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx5 | query idle gpu hours, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx6 | query allocated gpu counts, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx7 | query available gpu counts, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx8 | query total gpu hours by VC, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx9 | query allocated gpu hours by VC, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx10 | query healthy gpu hours by VC, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx11 | query allocated gpu hours, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx12 | query utilized gpu hours, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx13 | query idle gpu hours, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx14 | query allocated gpu hours by VC, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx15 | query idel gpu hours by VC, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx16 | query utilized gpu hours by VC, end time is now, offset is 1 day | cluster_job_metrics |
| f3c1idx17 | query job list, end time is now, offset is 1 day | cluster_job_metrics |

#### Job Metadata

This category involves questions about metadata associated with jobs, such as runtime details.

| id | question | solution
| --- | --- | --- |
| f3c3idx18 | query job meta data | job_metadata |

#### Dashboard

These questions focus on evaluating and monitoring cluster availability and reliability by analyzing aggregated performance metrics displayed on the dashboard.

| id | question | solution
| --- | --- | --- |
| f3c4idx0 | What is the average availability ratio for the pai-wcu endpoint in week 30? | dashboard |
| f3c4idx1 | Which cluster had the highest average availability ratio in week 30? | dashboard |
| f3c4idx2 | What is the minimum availability ratio recorded for the pai-scu endpoint in week 30? | dashboard |
| f3c4idx3 | How many clusters had zero availability in week 30? | dashboard |
| f3c4idx4 | What is the average percentage of allocated VMs across all clusters in week 30? | dashboard |
| f3c4idx5 | Which cluster had the highest percentage of unallocatable VMs in week 30? | dashboard |
| f3c4idx6 | How many total VMs were available in the CYS13PrdGPC02 cluster in week 31? | dashboard |
| f3c4idx7 | What is the percentage of "Available VMs (Empty)" in the LON64PrdGPC01 cluster in week 30? | dashboard |
| f3c4idx8 | What is the average job duration for hardware failures in week 30? | dashboard |
| f3c4idx9 | Which job had the longest duration in week 30, and what was its exit reason? | dashboard |
| f3c4idx10 | How many jobs failed due to software issues in week 30? | dashboard |
| f3c4idx11 | What is the maximum reaction time recorded for a job failure in week 30? | dashboard |
| f3c4idx12 | How many hardware-related node failures occurred in the pai-wcu endpoint in week 30? | dashboard |
| f3c4idx13 | What is the average node recycle time for cordon nodes in the CYS13PrdGPC02 cluster in week 30? | dashboard |
| f3c4idx14 | What is the MTBF (Mean Time Between Failures) for the CYS13PrdGPC02 cluster in week 30? | dashboard |
| f3c4idx15 | How many node failures were categorized as "unknown" in the pai-we endpoint in week 30? | dashboard |
| f3c4idx16 | What is the most common reason for hardware failures in the pai-wcu endpoint in week 30? | dashboard |
| f3c4idx17 | How many node failures were attributed to "NodeCrash" in the pai-scu endpoint in week 30? | dashboard |
| f3c4idx18 | What is the breakdown of node failure categories (hardware, platform, user, unknown) for the pai-wcu endpoint in week 30? | dashboard |
| f3c4idx19 | How many node failures were categorized as "uncategorized" across all endpoints in week 30? | dashboard |
| f3c4idx20 | What is the average availability ratio for the cluster CYS13PrdGPC02 in Week 27? | dashboard |
| f3c4idx21 | Which cluster had the highest percentage of allocated VMs in Week 22? | dashboard |
| f3c4idx22 | What was the most common reason for node failures? | dashboard |
| f3c4idx23 | What is the Mean Time Between Failures (MTBF) for the cluster CYS13PrdGPC02 in Week 27? | dashboard |
| f3c4idx24 | What is the average reaction time for hardware failures in Week 27? | dashboard |
| f3c4idx25 | How many job interruptions occurred due to hardware failures, and what was the average duration of these interruptions? | dashboard |
| f3c4idx26 | Which cluster had the highest percentage of unallocatable VMs in Week 27? | dashboard |
| f3c4idx27 | What was the total number of hardware-related node failures in Week 27 across all endpoints? | dashboard |
| f3c4idx28 | What was the node recycle time for cordon nodes in the CYS13PrdGPC02 cluster in Week 25? | dashboard |
| f3c4idx29 | What was the average availability ratio for the cluster CYS13PrdGPC02 in Week 27? | dashboard |
