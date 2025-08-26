# Introduction 
This repo is a model proxy which provides one unique endpoint by redirecting users' request to multi openai model endpoints. 

* It can serve requests of chat models and embedding models. 
* The target openai model endpoints can be in [azure spec](https://learn.microsoft.com/en-us/azure/ai-services/openai/reference) and [openai spec](https://platform.openai.com/docs/api-reference/)
* 

# Getting Started

## Without docker
1. Install golang >= 1.20
2. Build. The build script is located at `./scripts/build.sh`
3. Create a config file. There is an example config json file in `./config.json.example`
3. Run the proxy: `./bin/AIMiciusModelProxy --config ./bin/config.json`. You can refer to the script: ./scripts/runall.sh

## With docker
1. Install docker
2. Build. Run the `./scripts/build-docker.sh`
3. Create a config file. There is an example config json file in ./config.json.example
4. Run by docker. The secript is located at `./scripts/run-docker.sh`. For example `run-docker.sh -c <path to config.json> -p <host_port:docker_port>`. The `docker_port` should be the same with the value of `port` in the config json file.


# Configuration File Documentation

### Server

* `host`: The IP address where the server is hosted. Default is "0.0.0.0", which means all IPv4 addresses on the local machine.
* `port`: The port number on which the server is running.
* `retry`: The number of times to retry a failed request.
* `access_keys`: The keys that are allowed to access the server. It can be unset, or set as a list or a mapping:
  * If the item is not set, all keys are allowed.
  * If the item is a list, only the keys in the list are allowed.
  * If the item is a mapping, the keys in the mapping are allowed, and the values are the deadlines for the keys in date (in this format: "2006-01-02"), like {"key1": "2024-08-15"}

### Log 

* `log_storage`: Contains information about where to store logs.
  * `local_folder`: The path to the local folder where logs are stored.
  * `azure_storage`: Contains information about Azure storage if logs are stored in Azure.
    * `url`: The URL of the Azure storage, including the <sas_token>.
    * `container`: The name of the Azure storage container.
    * `path`: The path within the Azure storage where logs are stored.
* `trace_related_keys`: the keys that will be logged in trace to identify the trace, which will be and filtered in the api request

### Endpoints

* `azure_spec`: An array of objects, each representing a different Azure endpoint.
  * `url`: The URL of the Azure endpoint.
  * `key`: The key for the Azure endpoint.
  * `version`: The version of the Azure endpoint.
  * `chat`: An array of chat models available at this endpoint.
  * `embeddings`: An array of embedding models available at this endpoint.
* `openai_spec`: An array of objects, each representing a different OpenAI endpoint.
  * `url`: The URL of the OpenAI endpoint.
  * `key`: The key for the OpenAI endpoint.
  * `chat`: An array of chat models available at this endpoint.
  * `embeddings`: An array of embedding models available at this endpoint.