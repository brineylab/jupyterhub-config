#!/bin/bash
# 01_microk8s-setup.sh
# Installs and configures microk8s addons, the NFS CSI driver, and storage resources.
# Run on the HEAD NODE only.
# Usage: ./01_microk8s-setup.sh [dev|mcnulty|blackpearl]
set -euo pipefail

CLUSTER="${1:-}"
if [[ -z "$CLUSTER" ]]; then
  echo "Usage: $0 [dev|mcnulty|blackpearl]"
  exit 1
fi

# ── Cluster-specific config ──────────────────────────────────────────────────
case "$CLUSTER" in
  dev)
    METALLB_IP="172.29.180.116-172.29.180.116"
    ;;
  mcnulty)
    METALLB_IP="172.29.180.119-172.29.180.119"
    ;;
  blackpearl)
    METALLB_IP="172.29.80.65-172.29.80.65"   # update if different
    ;;
  *)
    echo "Unknown cluster: $CLUSTER"
    exit 1
    ;;
esac

echo "==> Setting up microk8s for cluster: $CLUSTER"

# ── 1. microk8s addons ───────────────────────────────────────────────────────
echo "==> [1/3] Enabling microk8s addons..."

# Enable DNS, providing Scripps' DNS servers
microk8s enable dns:172.29.40.10,172.29.40.9

# Enable ingress, metrics-server, and community addons
# NOTE: make sure nvidia drivers are installed on all GPU servers before enabling gpu!
# The gpu addon is currently disabled — uncomment to enable.
microk8s enable community
microk8s enable ingress
microk8s enable metrics-server
microk8s enable gpu

# Enable metallb for the load balancer.
# The IP range should be a single IP that resolves to the load balancer for the cluster.
microk8s enable "metallb:${METALLB_IP}"

# ── 2. Helm + NFS CSI driver ─────────────────────────────────────────────────
echo "==> [2/3] Installing Helm and NFS CSI driver..."

# NOTE: The NFS volume(s) to be used must be pre-configured separately — kubernetes just mounts them.
# All nodes on the cluster need to be whitelisted on the storage nodes (added to /etc/exports).
# See the repo README or Notion for details on configuring storage nodes.

# Install helm
microk8s enable helm3
grep -qxF "alias helm='microk8s helm3'" ~/.bashrc \
  || echo "alias helm='microk8s helm3'" >> ~/.bashrc
# shellcheck disable=SC1090
source ~/.bashrc

# Get the helm repo for the NFS CSI driver and install it
microk8s helm3 repo add csi-driver-nfs \
  https://raw.githubusercontent.com/kubernetes-csi/csi-driver-nfs/master/charts
microk8s helm3 repo update

microk8s helm3 install csi-driver-nfs csi-driver-nfs/csi-driver-nfs \
  --namespace kube-system \
  --set kubeletDir=/var/snap/microk8s/common/var/lib/kubelet

# ── 3. Storage classes, PVs, PVCs ────────────────────────────────────────────
echo "==> [3/3] Applying storage resources..."

# Clone the GitHub repo that has all of the custom resource definitions (CRDs) we need
if [[ ! -d jupyterhub-config ]]; then
  git clone https://github.com/brineylab/jupyterhub-config
fi
cd jupyterhub-config

# Create the jupyterhub namespace
kubectl apply -f hub/jupyterhub_namespace.yaml

# In addition to the default NFS volume JupyterHub uses for dynamic volumes,
# we set up storage classes (SCs), persistent volumes (PVs), and persistent
# volume claims (PVCs) for other data volumes (sequencing runs, shared storage, etc).

# Apply storage resources common to all clusters
kubectl apply -f storage/avon.yaml # novaseq & nextseq
kubectl apply -f storage/stringer.yaml # ont
kubectl apply -f storage/wallace.yaml # references

# Apply cluster-specific storage resources
case "$CLUSTER" in
  dev)
    kubectl apply -f storage/davyjones.yaml # shared drive
    kubectl apply -f storage/arwen-jh.yaml # user pvcs
    ;;
  mcnulty)
    kubectl apply -f storage/davyjones-mlnx.yaml # shared drive
    kubectl apply -f storage/wallace-jh.yaml # user pvcs
    ;;
  blackpearl)
    kubectl apply -f storage/davyjones.yaml # shared drive
    kubectl apply -f storage/sparrow-jh.yaml # user pvcs
    kubectl apply -f storage/sparrow.yaml # sparrow workspace
    kubectl apply -f storage/cedric.yaml # cedric workspace
    ;;
esac

echo ""
echo "✓ microk8s setup complete for cluster: $CLUSTER"
echo "  Next: run 02_node-setup.sh to add and label worker nodes."
