#!/bin/bash
set -x
counter=0
while ! nslookup nexusstaticsa.blob.core.windows.net &> /dev/null
do
    counter=$((counter+1))
    if [ $counter -ge 600 ]; then
        echo "DNS is not ready after waiting for 10 minutes."
        exit 1
    fi
    echo "Waiting for DNS..."
    sleep 1
done
echo "DNS is ready!"
