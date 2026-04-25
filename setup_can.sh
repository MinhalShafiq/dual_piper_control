#!/bin/bash
# Setup CAN interface for dual piper arm control.
# Both arms share ONE CAN bus, so only one interface needed.
#
# Usage: sudo bash setup_can.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================
# CONFIGURATION
# ============================================================
CAN_NAME="can0"
BITRATE=1000000
# Optional: USB address (find with: sudo ethtool -i can0 | grep bus-info)
# USB_ADDRESS="1-3:1.0"
# ============================================================

echo "========== Dual Piper CAN Setup =========="

if [ -n "$USB_ADDRESS" ]; then
    bash "$SCRIPT_DIR/piper_sdk/can_activate.sh" "$CAN_NAME" "$BITRATE" "$USB_ADDRESS"
else
    bash "$SCRIPT_DIR/piper_sdk/can_activate.sh" "$CAN_NAME" "$BITRATE"
fi

echo ""
echo "CAN interface:"
ip -br link show type can
echo "========== Setup Complete =========="
