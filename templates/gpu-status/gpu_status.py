#!/usr/bin/env python3
from flask import Flask, jsonify
from flask_cors import CORS
import subprocess
import json

app = Flask(__name__)
CORS(app)

def get_gpu_requests():
    result = subprocess.run(
        ['microk8s', 'kubectl', 'get', 'pods', '--all-namespaces', '-o', 'json'],
        capture_output=True, text=True
    )
    pods = json.loads(result.stdout)
    
    gpu_requests = {}
    for item in pods['items']:
        node = item['spec']['nodeName']
        for container in item['spec']['containers']:
            requests = container.get('resources', {}).get('requests', {})
            if 'nvidia.com/gpu' in requests:
                gpu_requests.setdefault(node, 0)
                gpu_requests[node] += int(requests['nvidia.com/gpu'])
    
    return gpu_requests

def get_node_capacity_and_profile():
    result = subprocess.run(
        ['microk8s', 'kubectl', 'get', 'nodes', '-o', 'json'],
        capture_output=True, text=True
    )
    nodes = json.loads(result.stdout)
    
    node_info = {}
    for item in nodes['items']:
        node_name = item['metadata']['name']
        node_info[node_name] = {
            'node_profile': item['metadata']['labels'].get('node_profile', 'unknown'),
            'capacity': int(item['status']['capacity'].get('nvidia.com/gpu', 0)),
        }
    
    return node_info

# group by node profile (aka, gpu type)
def combine_and_group(node_info, gpu_requests):
    grouped_info = {}
    for node, info in node_info.items():
        profile = info['node_profile']
        
        # adds profiles not yet accounted for
        if profile not in grouped_info:
            grouped_info[profile] = {
                'node_profile': profile,
                'capacity': 0,
                'total_gpu_requests': 0
            }
        
        grouped_info[profile]['capacity'] += info['capacity']
        grouped_info[profile]['total_gpu_requests'] += gpu_requests.get(node, 0)
    
    return grouped_info

@app.route('/gpu_status')
def gpu_status():
    gpu_requests = get_gpu_requests()
    node_info = get_node_capacity_and_profile()
    grouped_info = combine_and_group(node_info, gpu_requests)

    # Format output as a list of dicts
    output = [
        {
            'node_profile': value['node_profile'],
            'capacity': value['capacity'],
            'total_gpu_requests': value['total_gpu_requests']
        }
        for value in grouped_info.values()
    ]

    # Sort the list of dicts by the 'node_profile' field
    output = sorted(output, key=lambda x: x['node_profile'])
    
    return jsonify(output)

if __name__ == "__main__":
    # Running the Flask app on all interfaces on port 5000
    app.run(host='0.0.0.0', port=5000)

