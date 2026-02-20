#!/usr/bin/env python3
from flask import Flask, jsonify
from flask_cors import CORS
import subprocess
import json

app = Flask(__name__)
CORS(app)


def get_cpu_requests():
    result = subprocess.run(
        ["microk8s", "kubectl", "get", "pods", "-n", "jupyterhub", "-o", "json"],
        capture_output=True,
        text=True,
    )
    pods = json.loads(result.stdout)

    cpu_requests = {}
    for item in pods["items"]:
        node = item["spec"].get("nodeName")
        user = item["metadata"].get("labels", {}).get("hub.jupyter.org/username", "")

        for container in item["spec"]["containers"]:
            requests = container.get("resources", {}).get("requests", {})
            if "cpu" in requests:
                entry = cpu_requests.setdefault(node, {"users": set(), "requested_cpu": 0})
                entry["users"].add(user)
                entry["requested_cpu"] += int(requests["cpu"])

    return cpu_requests


def get_cpu_nodes():
    result = subprocess.run(
        ["microk8s", "kubectl", "get", "nodes", "-o", "json"],
        capture_output=True,
        text=True,
    )
    nodes = json.loads(result.stdout)

    node_info = {}
    for item in nodes["items"]:
        node_name = item["metadata"]["name"]
        
        node_profile = item["metadata"]["labels"].get("node_profile", "unknown")
        if node_profile != "cpu":
            continue

        # check if node is schedulable
        is_unschedulable = item.get("spec", {}).get("unschedulable", False)
        capacity = (
            0
            if is_unschedulable
            else int(item["status"]["capacity"].get("cpu", 0))
        )

        node_info[node_name] = capacity

    return node_info


def combine_and_group(node_info, cpu_requests):
    users_all = set()
    used_nodes = 0
    for node, capacity in node_info.items():
        if capacity == 0:
            continue

        req_entry = cpu_requests.get(node)
        if req_entry:
            used_nodes += 1
            users = req_entry.get("users", [])
            users_all.update(users)

    available_nodes = len(node_info) - used_nodes

    return {
        "available_cpu_nodes": available_nodes,
        "used_cpu_nodes": used_nodes,
        "users_using_nodes": sorted(users_all)
    }


@app.route("/cpu_status_bynode")
def cpu_status():
    cpu_requests = get_cpu_requests()
    node_info = get_cpu_nodes()
    combined = combine_and_group(node_info, cpu_requests)

    return jsonify(combined)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
