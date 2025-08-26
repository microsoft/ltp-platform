#!/bin/bash
# This script is used to run the docker after building

usage (){
    echo "Usage: $0 [-p <port>] [-n <name>] [-c <config>] [-h]"
    echo "  -p <server_port:docker_port>: the port of the server : the port of the docker"
    echo "  -c <config> : Path to the proxy config file"
    echo "  -h          : Show usage"
    exit 1
}

# Set the default values
PORT=9999:8999
CONFIG=./bin/config.json

# Parse the command line arguments
while getopts "p:c:h" opt; do
    case $opt in
        p)
            PORT=$OPTARG
            ;;
        c)
            CONFIG=$OPTARG
            ;;
        h)
            usage
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            usage
            ;;
    esac
done

# Check if the config file exists
if [ ! -f $CONFIG ]; then
    echo "Config file not found: $CONFIG"
    usage
fi

# Get the absolute path of the config file
CONFIG=$(cd $(dirname $CONFIG) && pwd -P)/$(basename $CONFIG)

# Run the docker
docker run -d \
    -p $PORT \
    --mount type=bind,source=$CONFIG,target=/config.json \
    modelproxy:latest \
    ./bin/modelproxy --config /config.json