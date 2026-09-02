#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl tar rsync ca-certificates
python3 -m pip install -q --break-system-packages jsonschema referencing
mkdir -p /opt/p2 /root/.local/bin
if ! command -v agent >/dev/null 2>&1 && ! command -v cursor-agent >/dev/null 2>&1; then
  curl -fsSL https://cursor.com/install | bash || true
fi
echo "BOOTSTRAP-OK"
python3 --version
ls -lh /opt/p2/ast-integrate/command-center/ready_units.py
