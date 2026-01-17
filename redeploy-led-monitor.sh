#!/usr/bin/env bash
#
# Helper script: redeploy and restart the LED monitor services.
#
# - Installs the latest led-monitor.service and led-monitor-web.service unit files
# - Reloads systemd
# - Restarts both services
# - Shows a short status summary

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$ROOT_DIR"

echo "Copying systemd unit files..."
if [ -f "led-monitor.service" ]; then
    sudo cp led-monitor.service /etc/systemd/system/led-monitor.service
    echo "  ✓ led-monitor.service"
fi

if [ -f "led-monitor-web.service" ]; then
    sudo cp led-monitor-web.service /etc/systemd/system/led-monitor-web.service
    echo "  ✓ led-monitor-web.service"
fi

echo
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo
echo "Restarting services..."
if systemctl is-enabled led-monitor.service >/dev/null 2>&1; then
    echo "  Restarting led-monitor.service..."
    sudo systemctl restart led-monitor.service
fi

if systemctl is-enabled led-monitor-web.service >/dev/null 2>&1; then
    echo "  Restarting led-monitor-web.service..."
    sudo systemctl restart led-monitor-web.service
fi

echo
echo "Service status:"
if systemctl is-active led-monitor.service >/dev/null 2>&1; then
    echo
    echo "led-monitor.service:"
    sudo systemctl status led-monitor.service --no-pager -l | sed -n '1,10p'
fi

if systemctl is-active led-monitor-web.service >/dev/null 2>&1; then
    echo
    echo "led-monitor-web.service:"
    sudo systemctl status led-monitor-web.service --no-pager -l | sed -n '1,10p'
fi


