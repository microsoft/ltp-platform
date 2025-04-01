import requests
import yaml
import sys

def modify(yaml_url):
    # Download the YAML file
    response = requests.get(yaml_url)
    yaml_content = response.text

    # Load all YAML documents
    documents = list(yaml.safe_load_all(yaml_content))

    # Modify the specific YAML document
    for data in documents:
        if not data:
            continue
        if 'metadata' in data and data['metadata'].get('name') == 'csi-blob-node':
            data['metadata']['name'] = "csi-blob-node-unmanaged"
            data['spec']['selector']['matchLabels']['app'] = "csi-blob-node-unmanaged"
            data['spec']['template']['metadata']['labels']['app'] = "csi-blob-node-unmanaged"

            # Create the new node affinity configuration
            node_affinity_config = {
                'matchExpressions': [
                    {
                        'key': 'kubernetes.azure.com/managed',
                        'operator': 'In',
                        'values': ["False", "false"]
                    },
                    {
                        'key': 'kubernetes.io/os',
                        'operator': 'In',
                        'values': ['linux']
                    }
                ]
            }

            # Add the new node affinity configuration
            node_selector_terms = data['spec']['template']['spec']['affinity']['nodeAffinity']['requiredDuringSchedulingIgnoredDuringExecution']['nodeSelectorTerms']
            node_selector_terms[0]['matchExpressions'].extend(node_affinity_config['matchExpressions'])

    # Convert the modified YAML content back to a string
    modified_yaml_content = yaml.dump_all(documents, default_flow_style=False)
    return modified_yaml_content

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://raw.githubusercontent.com/kubernetes-sigs/blob-csi-driver/refs/heads/master/deploy/csi-blob-node.yaml"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "modified_csi-blob-node.yaml"
    modified_yaml_content = modify(url)
    with open(output_file, 'w') as yaml_file:
        yaml_file.write(modified_yaml_content)
    print(f"Modified YAML content saved to {output_file}")