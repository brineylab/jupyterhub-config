#!/bin/bash
# 03_jupyterhub-setup.sh
# Configures auth, secrets, and installs JupyterHub via Helm.
# Run on the HEAD NODE only.
# Usage: ./03_jupyterhub-setup.sh [dev|mcnulty|blackpearl]
#
# NOTE: For first-time setup, run setup_postgres.sh before this script
# to initialize the PostgreSQL database.
set -euo pipefail

prompt_password() {
  local prompt="$1" var="$2"
  while true; do
    read -rsp "${prompt}: " pw1 && echo
    read -rsp "Confirm: " pw2 && echo
    if [[ "$pw1" == "$pw2" ]]; then
      eval "$var='$pw1'"
      break
    fi
    echo "Passwords do not match, try again."
  done
}

CLUSTER="${1:-}"
if [[ -z "$CLUSTER" ]]; then
  echo "Usage: $0 [dev|mcnulty|blackpearl]"
  exit 1
fi

# ── Cluster-specific config ──────────────────────────────────────────────────
VALID_CLUSTERS=("dev" "mcnulty" "blackpearl")
if [[ ! " ${VALID_CLUSTERS[*]} " =~ " ${CLUSTER} " ]]; then
  echo "Unknown cluster: $CLUSTER (must be one of: ${VALID_CLUSTERS[*]})"
  exit 1
fi

CONFIG_FILE="${CLUSTER}_config.yaml"

echo "==> Setting up JupyterHub for cluster: $CLUSTER"

# ── 1. ConfigMaps & status services ─────────────────────────────────────────
echo "==> [1/4] Applying ConfigMaps and status services..."

# Apply custom ConfigMaps for user authentication (gpu vs regular users)
# and to customize the home and spawn pages.
# --dry-run=client -o yaml | kubectl apply -f - is needed when updating
# the configmap from a file/directory (not required for initial creation,
# but safe to use either way).
kubectl create configmap templates \
  --from-file=hub/templates/ -n jupyterhub \
  --dry-run=client -o yaml | kubectl apply -f -

# Install required Python packages for the GPU/CPU status services,
# which expose resource availability on the spawn page.
sudo apt install -y python3-pip
pip install flask flask-cors gunicorn

# Install the systemd service files and start/enable the services.
# The services run gpu_status_bynode.py (port 5000) and cpu_status_bynode.py (port 5001).
# Check status with: sudo systemctl status gpu-status.service
# Or curl: http://<HEAD_NODE_IP>:5000/gpu_status_bynode
sudo install -o root -g root -m 0644 ./hub/spawn_status/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart gpu-status.service
sudo systemctl restart cpu-status.service
sudo systemctl enable gpu-status.service
sudo systemctl enable cpu-status.service

# ── 2. Auth (LLDAP) ──────────────────────────────────────────────────────────
echo "==> [2/4] Setting up LLDAP authentication..."

# Copy the CA cert from the LLDAP node (needed for TLS)
scp brineylab@namond.scripps.edu:/home/brineylab/lldap/certs/brineylab-ca.crt \
  ./auth/certs/brineylab-ca.crt

# Create a ConfigMap with the cert
kubectl create configmap lldap-ca \
  --from-file=ca.crt=./auth/certs/brineylab-ca.crt \
  -n jupyterhub \
  --dry-run=client -o yaml | kubectl apply -f -

# Create a secret with the LLDAP bind password (sssd user)
prompt_password "Enter LLDAP bind password" LLDAP_PASSWORD
kubectl create secret generic lldap-bind-secret \
  --from-literal=password="${LLDAP_PASSWORD}" \
  -n jupyterhub \
  --dry-run=client -o yaml | kubectl apply -f -
unset LLDAP_PASSWORD

# ── 3. PostgreSQL secret ─────────────────────────────────────────────────────
echo "==> [3/4] Configuring PostgreSQL secret..."

# We use PostgreSQL instead of the default SQLite because our storage is on NFS,
# which is not compatible with SQLite. See: https://jupyterhub.readthedocs.io/en/latest/explanation/database.html
#
# NOTE: DB creation only needs to happen on first-time setup!
# If PostgreSQL has been set up before, just make sure the service is running.
# Run setup_postgres.sh for first-time setup.

# Verify the jupyterhub_db database is reachable
if ! psql -U brineylab -d jupyterhub_db -c '\q' 2>/dev/null; then
  echo "Error: could not connect to jupyterhub_db. Make sure the database is running and the password is correct."
  echo "  For first-time setup, run setup_postgres.sh first."
  echo "  Otherwise: sudo systemctl start postgresql"
  exit 1
fi

# Prompt for the password to create the k8s secret
prompt_password "Enter PostgreSQL password" POSTGRES_PASSWORD

# Create the k8s secret with the database password (safe to re-run)
kubectl create secret generic postgres-secret \
  --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  -n jupyterhub \
  --dry-run=client -o yaml | kubectl apply -f -
unset POSTGRES_PASSWORD

# ── 4. Install JupyterHub via Helm ───────────────────────────────────────────
echo "==> [4/4] Installing JupyterHub..."

# Add the JupyterHub helm repo
helm repo add jupyterhub https://jupyterhub.github.io/helm-chart/
helm repo update

# Install JupyterHub. The initial run takes a while since it downloads
# the containers — the deep learning container is particularly large.
helm upgrade \
  --cleanup-on-fail \
  --install jupyterhub jupyterhub/jupyterhub \
  --namespace jupyterhub \
  --create-namespace \
  -f config/base_config.yaml \
  -f "config/${CONFIG_FILE}" \
  --timeout 30m0s \
  --version 4.3.2

echo ""
echo "✓ JupyterHub setup complete for cluster: $CLUSTER"
