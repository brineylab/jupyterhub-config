#!/bin/bash
# 02_node-setup.sh
# Adds and labels worker nodes for the cluster.
# Run on the HEAD NODE only.
# Usage: ./02_node-setup.sh [dev|mcnulty|blackpearl]
#
# NOTE: joining nodes requires SSH into each worker node — see instructions below.
set -euo pipefail

CLUSTER="${1:-}"
if [[ -z "$CLUSTER" ]]; then
  echo "Usage: $0 [dev|mcnulty|blackpearl]"
  exit 1
fi

# ── 1. Add nodes ─────────────────────────────────────────────────────────────
# For each node to be added, run the following on the HEAD NODE to generate
# a join token, then SSH into the worker node and run the join command.
#
# On the head node:
#   microk8s add-node
#
# This will output a join command like:
#   microk8s join 192.168.1.X:25000/<token> 
#
# SSH into the worker node and run the join command using the MELLANOX IP
# (the last command in the output, using the 192.168.1.X address).
# Repeat for each additional node.
#
# Make sure the IP address and hostname for all nodes are present in
# /etc/hosts on every node before joining, using their mellanox IPs.

echo "==> Have all worker nodes been joined to the cluster? (y/n)"
read -r JOINED
if [[ "$JOINED" != "y" ]]; then
  echo "Please join all worker nodes before continuing."
  echo "See the comments in this script or the Notion for instructions."
  exit 1
fi

# ── 2. Label nodes ───────────────────────────────────────────────────────────
# Nodes are labeled so that pods get scheduled on the correct node for the
# requested resources (e.g. gpu type, cpu-only, etc).
echo "==> [1/1] Labeling nodes..."

case "$CLUSTER" in
  dev)
    microk8s kubectl label nodes arwen node_profile="low-cpu" --overwrite
    microk8s kubectl label nodes galadriel node_profile="3090" --overwrite
    ;;
  mcnulty)
    microk8s kubectl label nodes ellis jay node_profile="A6000" --overwrite
    microk8s kubectl label nodes michael rawls node_profile="L40S" --overwrite
    microk8s kubectl label nodes bunk lester kima beadie node_profile="cpu" --overwrite
    microk8s kubectl label nodes carcetti slim cutty partlow bubbles frank bodie ziggy node_profile="low-cpu" --overwrite
    microk8s kubectl label nodes namond node_profile="headnode" --overwrite
    ;;
  blackpearl)
    microk8s kubectl label nodes sparrow node_profile="headnode" --overwrite
    microk8s kubectl label nodes swann turner node_profile="L40S" --overwrite
    microk8s kubectl label nodes cedric node_profile="A100" --overwrite
    ;;
  *)
    echo "Unknown cluster: $CLUSTER"
    exit 1
    ;;
esac

echo ""
echo "✓ Node setup complete for cluster: $CLUSTER"
echo "  Verify nodes are ready with: kubectl get nodes"
echo "  Next: run 03_jupyterhub-setup.sh to install JupyterHub."
