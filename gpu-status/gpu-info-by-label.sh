#!/bin/bash

# Get GPU requests per node
requests=$(microk8s kubectl get pods --all-namespaces -o json |
jq '[.items[] | select(.spec.containers[].resources.requests["nvidia.com/gpu"] != null) | {node: .spec.nodeName, gpu_requests: .spec.containers[].resources.requests["nvidia.com/gpu"]}] |
    group_by(.node) |
    map({node: .[0].node, total_gpu_requests: map(.gpu_requests | tonumber) | add})')

# Get node capacity and node_profile label
capacity=$(microk8s kubectl get nodes -o json |
jq '[.items[] | {
  node: .metadata.name,
  capacity: (.status.capacity["nvidia.com/gpu"] | tonumber),
  node_profile: .metadata.labels."node_profile"
}]')

# Combine and group by node_profile
echo "$capacity" | jq --argjson requests "$requests" '
  # Combine node capacity with GPU requests
  reduce .[] as $node ({}; 
    .[$node.node_profile] += {
      node_profile: $node.node_profile,
      nodes: (if .[$node.node_profile] then .[$node.node_profile].nodes + [$node.node] else [$node.node] end),
      capacity: (if .[$node.node_profile] then .[$node.node_profile].capacity + $node.capacity else $node.capacity end),
      total_gpu_requests: (if .[$node.node_profile] then .[$node.node_profile].total_gpu_requests + ($requests[] | select(.node == $node.node) | .total_gpu_requests) else ($requests[] | select(.node == $node.node) | .total_gpu_requests) end)
    }
  ) |
  to_entries | map(.value)
'
