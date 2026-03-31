# JupyterHub Setup

Configuration and setup scripts for deploying JupyterHub on microk8s. Currently supports three clusters: `dev`, `mcnulty`, and `blackpearl`.

---

## Prerequisites

Before running any setup scripts, make sure:
- All nodes are running Ubuntu with SSH access
- NVIDIA drivers are installed on all GPU nodes
- NFS volumes are pre-configured on storage nodes and all cluster nodes are whitelisted in `/etc/exports` (see Notion for details)
- The `jupyterhub-config` repo is cloned on the head node

---

## Setup

### Step 0 — All nodes: system dependencies + microk8s

Run on **every node** in the cluster (head and workers):

```bash
./00_node-prereqs.sh
```

This will install system dependencies and microk8s. After it completes, you will be prompted to **disconnect and reconnect your SSH session**, then re-run:

```bash
./00_node-prereqs.sh --post-reconnect
```

---

### Step 1 — Head node: microk8s addons + storage

Run on the **head node** only:

```bash
./01_microk8s-setup.sh [dev|mcnulty|blackpearl]
```

This will:
- Enable microk8s addons (DNS, ingress, metrics-server, metallb, gpu)
- Install Helm and the NFS CSI driver
- Apply storage classes, persistent volumes, and persistent volume claims

---

### Step 2 — Head node: add + label worker nodes

Joining nodes requires SSH into each worker node. For each node to be added, run the following on the **head node** to generate a join token:

```bash
microk8s add-node
```

SSH into the worker node and run the join command using the **Mellanox IP** (the last command in the output). Repeat for each additional node.

> **Note:** Make sure the IP address and hostname for all nodes are present in `/etc/hosts` on every node before joining, using their Mellanox IPs.

Once all nodes have joined, run on the **head node**:

```bash
./02_node-setup.sh [dev|mcnulty|blackpearl]
```

This will label all nodes with the correct `node_profile` so that pods are scheduled on the correct node for the requested resources.

Verify nodes are ready and correctly labeled:
```bash
kubectl get nodes -L node_profile
```

---

### Step 2.5 — Head node: PostgreSQL (first-time setup only)

> Skip this step if PostgreSQL has been set up before — just make sure the service is running (`sudo systemctl start postgresql`).

```bash
./setup_postgres.sh <mellanox-head-ip>
# e.g. ./setup_postgres.sh 172.29.180.195
```

---

### Step 3 — Head node: JupyterHub

```bash
./03_jupyterhub-setup.sh [dev|mcnulty|blackpearl]
```

This will:
- Apply custom ConfigMaps for the hub templates
- Install and enable the GPU/CPU status services
- Set up LLDAP authentication
- Create the PostgreSQL k8s secret
- Install JupyterHub via Helm

> **Note:** The initial Helm install takes a while — the deep learning container is particularly large.

---

## Administration

### Updating JupyterHub

To update the JupyterHub config or upgrade the Helm chart version, run the helm upgrade command:
```bash
helm upgrade \
  --cleanup-on-fail \
  --install jupyterhub jupyterhub/jupyterhub \
  --namespace jupyterhub \
  --create-namespace \
  -f base_config.yaml \
  -f "${CONFIG_FILE}" \
  --timeout 30m0s \
  --version 4.3.2
```

To update only the hub templates ConfigMap:

```bash
kubectl create configmap templates \
  --from-file=hub/templates/ -n jupyterhub \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl rollout restart deployment hub -n jupyterhub
```

### Managing users

Users and groups are managed via LLDAP. See the [LLDAP repo](https://github.com/brineylab/lldap) for instructions on adding users and assigning them to groups (`admin`, `gpu`, `regular`).

After making changes in LLDAP, restart the hub to pick up the updated group memberships:

```bash
kubectl rollout restart deployment hub -n jupyterhub
```

### Checking cluster status

```bash
# pod status
kubectl get pods -n jupyterhub

# GPU availability
curl http://localhost:5000/gpu_status_bynode

# CPU availability
curl http://localhost:5001/cpu_status_bynode

# status service logs
sudo systemctl status gpu-status.service
sudo systemctl status cpu-status.service
```
