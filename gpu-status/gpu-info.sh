#!/bin/bash

# Get GPU requests per node
requests=$(microk8s kubectl get pods --all-namespaces -o json |
jq '[.items[] | select(.spec.containers[].resources.requests["nvidia.com/gpu"] != null) | {node: .spec.nodeName, gpu_requests: .spec.containers[].resources.requests["nvidia.com/gpu"]}] |
    group_by(.node) |
    map({node: .[0].node, total_gpu_requests: map(.gpu_requests | tonumber) | add})')

# Get node capacity, labels, and extract node_profile label
capacity=$(microk8s kubectl get nodes -o json |
jq '[.items[] | {
  node: .metadata.name,
  capacity: (.status.capacity["nvidia.com/gpu"] | tonumber),
  labels: .metadata.labels."node_profile"
}]')

# Combine both pieces of information
echo "$capacity" | jq --argjson requests "$requests" '
  [
    .[] |
    {
      node: .node,
      node_profile: .labels,
      capacity: .capacity
    } as $node |
    $requests[] | select(.node == $node.node) |
    $node + {total_gpu_requests: .total_gpu_requests}
  ]'
