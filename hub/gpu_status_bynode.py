#!/usr/bin/env python3
from flask import Flask, jsonify
from flask_cors import CORS
import subprocess
import json

app = Flask(__name__)
CORS(app)


def get_gpu_requests():
    result = subprocess.run(
        ["microk8s", "kubectl", "get", "pods", "--all-namespaces", "-o", "json"],
        capture_output=True,
        text=True,
    )
    pods = json.loads(result.stdout)

    gpu_requests = {}
    for item in pods["items"]:
        node = item["spec"]["nodeName"]
        for container in item["spec"]["containers"]:
            requests = container.get("resources", {}).get("requests", {})
            if "nvidia.com/gpu" in requests:
                gpu_requests.setdefault(node, 0)
                gpu_requests[node] += int(requests["nvidia.com/gpu"])

    return gpu_requests


def get_node_capacity_and_profile():
    result = subprocess.run(
        ["microk8s", "kubectl", "get", "nodes", "-o", "json"],
        capture_output=True,
        text=True,
    )
    nodes = json.loads(result.stdout)

    node_info = {}
    for item in nodes["items"]:
        node_name = item["metadata"]["name"]

        # check if node is schedulable
        # then calculate GPU capacity
        is_unschedulable = item.get("spec", {}).get("unschedulable", False)
        capacity = (
            0
            if is_unschedulable
            else int(item["status"]["capacity"].get("nvidia.com/gpu", 0))
        )

        node_info[node_name] = {
            "node_profile": item["metadata"]["labels"].get("node_profile", "unknown"),
            "capacity": capacity,
        }

    return node_info


# group by node
def combine_and_group(node_info, gpu_requests):
    combined_info = []
    for node, info in node_info.items():
        if info["node_profile"] not in ["cpu", "headnode"]:

            # zero out requests if capacity is 0
            # to prevent negative GPU availability
            requests = 0 if info["capacity"] == 0 else gpu_requests.get(node, 0)

            combined_info.append(
                {
                    "node_name": node.split(".")[0],
                    "node_profile": info["node_profile"],
                    "capacity": info["capacity"],
                    "total_gpu_requests": requests,
                }
            )

    return combined_info


@app.route("/gpu_status_bynode")
def gpu_status():
    gpu_requests = get_gpu_requests()
    node_info = get_node_capacity_and_profile()
    combined_info = combine_and_group(node_info, gpu_requests)

    # Format output as a list of dicts
    combined_info = sorted(combined_info, key=lambda x: x["node_name"])
    return jsonify(combined_info)


if __name__ == "__main__":
    # Running the Flask app on all interfaces on port 5000
    app.run(host="0.0.0.0", port=5000)
