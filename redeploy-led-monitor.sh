#!/usr/bin/env bash
#
# Helper script: redeploy and restart the LED monitor service.
#
# - Installs the latest led-monitor.service unit file
# - Reloads systemd
# - Restarts the service
# - Shows a short status summary

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$ROOT_DIR"

echo "Copying systemd unit..."
sudo cp led-monitor.service /etc/systemd/system/led-monitor.service

echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "Restarting led-monitor.service..."
sudo systemctl restart led-monitor.service

echo
echo "Service status:"
sudo systemctl status led-monitor.service --no-pager -l | sed -n '1,20p'


