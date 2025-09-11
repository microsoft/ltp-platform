# Instruction of model-proxy

## Overview

Model-proxy is a proxy service to forward requests from clients to different model jobs in LTP cluster. With one base url, client can access different models by specifying different model name in the request path, `model-proxy` service will forward the request to corresponding model job. If there are multiple jobs which are serving the same model, `model-proxy` will do load balancing among these jobs.

Workflow:

1. Client sends request to `model-proxy` service to list all models by `/v1/models` endpoint.
   - During the list request, `model-proxy` will query LTP REST server to get all model serving jobs which the user can access, and then list all models which are being served by these jobs.

2. Client sends request to `model-proxy` service to access a specific model by openai sepc api request format, e.g. `POST /v1/chat/completions` with request body containing model name.
   - During the access request, `model-proxy` will query LTP REST server to get all model serving jobs which are serving the requested model, and then forward the request to one of these jobs. If there are multiple jobs, `model-proxy` will do load balancing among these jobs.

## Configuration

### Requirements 

- LTP model serving jobs should be deployed in the LTP cluster, and names of these jobs must include `model-serving`.

- LTP model serving jobs should support openai spec api, e.g. `/v1/chat/completions` endpoint. And the api key which is configured in model-proxy service should be supported by these endpoints.

### Binary configuration

Model-proxy binary can be configured by flags:

- `--port`: the port that model-proxy service listens on, default is 9999
- `--retry`: the retry times when forwarding request to model job, default is 5
- `--logdir`: the directory to store log files, default is `./logs`
- `--modelkey`: the key which is used to request model serving jobs in the LTP cluster.

### Service configuration

```yaml
model-proxy:  
    port: 9999
    retry: 5
    modelkey: "ABCD1234"  # the api key to access model serving jobs
```
