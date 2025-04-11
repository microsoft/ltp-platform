# Service Building and Deployment

When services under './src' are updated, or related configuration files are changed, the following steps should be taken to ensure that the changes are reflected in the deployed service.

## 0. Prerequisites
- Ensure that you have the necessary permissions and environment to deploy the service. You can refer to [Service Setup](docs/service_setup_readme.md) for more details.
- Well configured the cluster configuration files. Service updating related configurations can be got by `./paictl.py config pull -o <config_folder>`. You can refer to [Service Setup](docs/service_setup_readme.md) for more details. 

## 1. Build the service

Build the service image: 

```bash
./build/pai_build.py build -c <your_config_folder> -s <your_service_name, or service list split by ' '> 
```

## 2. Push the service image to the registry 

The **docker registry** and image tag should be configured in `<your_config_folder>/services-configuration.yaml` file.

```bash
./build/pai_build.py push -c <your_config_folder> -i <your_service_name, or a list split by ' '>
```

## 3. Update the service

1. stop the related service by:
```bash
./paictl.py service stop -n <your_service_name, or a list split by ' '> 
```

2. If you have updated the configuration files, you need to update these configs and update the `cluster-configuration` service by:
```bash
./paictl.py config push -c <your_config_folder> 
./paictl.py service start -n cluster-configuration
```
and 

3. start the related service by:
```bash
./paictl.py service start -n <your_service_name, or a list split by ' '> 
```

Note: 

- If you have updated the `hivedscheduler` service, the `rest-server` service should be restarted after the `hivedscheduler` service is restarted.
- All commands calling `paictl.py` need user to input the cluster name for confirmation. 