#!/bin/bash
# setup_postgres.sh
# PostgreSQL first-time setup for JupyterHub.
#
# We have to setup a hub database using PostgreSQL (rather than using the default
# sqlite), because our storage is setup on NFS.
# See: https://jupyterhub.readthedocs.io/en/latest/explanation/database.html
#
# NOTE: you only need to run this script if this is the first time this server
# is being setup! If the PostgreSQL database has been setup before, just make
# sure the service is running and that the k8s secret with the database password
# is set.
#
# Run on the HEAD NODE only.
# Usage: ./setup_postgres.sh <database-node-ip>
# Preferably, the database-node-ip is the mellanox IP
#
# Examples:
#   dev:            ./setup_postgres.sh 172.29.180.195
#   mcnulty:        ./setup_postgres.sh 192.168.1.7
#   blackpearl:     ./setup_postgres.sh 192.168.1.3
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

HEAD_IP="${1:-}"

if [[ -z "$HEAD_IP" ]]; then
  echo "Usage: $0 <database-node-ip>"
  exit 1
fi

PG_CONF_DIR="/etc/postgresql/14/main"

# Make sure postgresql and postgresql-contrib are installed
echo "==> Installing PostgreSQL..."
sudo apt install -y postgresql postgresql-contrib

# Start and enable the PostgreSQL service
echo "==> Starting and enabling PostgreSQL service..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create the database and set user privileges
echo "==> Creating database and user..."
prompt_password "Enter password for PostgreSQL 'brineylab' user" PG_PASSWORD
sudo -u postgres psql <<EOF
CREATE DATABASE jupyterhub_db;
CREATE USER brineylab WITH PASSWORD '${PG_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE jupyterhub_db TO brineylab;
EOF
unset PG_PASSWORD

# Modify postgresql.conf to set the listen address.
# This should be the mellanox IP where the db is setup.
# (can also set to '*' to listen everywhere, but providing the mellanox IP is more secure)
echo "==> Configuring listen address in postgresql.conf..."
sudo sed -i "s/^#*listen_addresses\s*=.*/listen_addresses = '${HEAD_IP}'/" \
  "${PG_CONF_DIR}/postgresql.conf"

# Modify pg_hba.conf to add access rules.
# The first line (192.168.1.1/24) is not technically necessary for jupyterhub,
# but helps with debugging — uncomment if needed.
echo "==> Adding access rules to pg_hba.conf..."
cat <<EOF | sudo tee -a "${PG_CONF_DIR}/pg_hba.conf"

# JupyterHub access rules
# host    jupyterhub_db   brineylab       192.168.1.1/24        md5
host    jupyterhub_db   brineylab       ${HEAD_IP}/32           md5
host    jupyterhub_db   brineylab       10.1.0.0/16             md5
EOF

# Restart the service to apply changes
echo "==> Restarting PostgreSQL to apply changes..."
sudo systemctl restart postgresql

echo ""
echo "✓ PostgreSQL setup complete."
echo "  DB URL: postgresql://brineylab:@${HEAD_IP}:5432/jupyterhub_db"
