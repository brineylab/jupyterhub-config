#!/bin/bash
# 00_node-prereqs.sh
# Installs and configures system dependencies and microk8s.
# Run on ALL nodes in the cluster (head and workers).
#
# NOTE: This script requires one manual step — you must disconnect and
# reconnect your SSH session after the microk8s group is configured,
# then re-run this script with the --post-reconnect flag:
#   ./00_node-init.sh --post-reconnect
set -euo pipefail

POST_RECONNECT="${1:-}"

if [[ "$POST_RECONNECT" == "--post-reconnect" ]]; then

  # ── Post-reconnect: kube config & kubectl alias ──────────────────────────
  echo "==> Configuring kubectl..."

  mkdir -p ~/.kube
  sudo chown -f -R "$USER" ~/.kube
  microk8s config > ~/.kube/config

  # Alias the microk8s version of kubectl
  grep -qxF "alias kubectl='microk8s kubectl'" ~/.bashrc \
    || echo "alias kubectl='microk8s kubectl'" >> ~/.bashrc
  # shellcheck disable=SC1090
  source ~/.bashrc

  echo ""
  echo "✓ Node init complete."
  echo "  If this is the head node, run 01_microk8s-setup.sh next."
  echo "  If this is a worker node, wait for the head node to generate a join token."

else

  # ── 1. System dependencies ───────────────────────────────────────────────
  echo "==> [1/2] Installing system dependencies..."

  sudo apt update \
    && sudo apt upgrade -y \
    && sudo apt install -y openssh-server tmux git nfs-common vim btop htop

  # Allow SSH through the firewall
  sudo ufw allow ssh

  # ── 2. Install microk8s ──────────────────────────────────────────────────
  echo "==> [2/2] Installing microk8s..."

  sudo snap install microk8s --classic --channel=1.35/stable

  # Add the current user to the microk8s group and grant access to kubectl config files
  sudo usermod -a -G microk8s "$USER"

  echo ""
  echo "✓ System dependencies and microk8s installed."
  echo "  ACTION REQUIRED: disconnect and reconnect your SSH session, then re-run:"
  echo "    ./00_node-init.sh --post-reconnect"

fi
