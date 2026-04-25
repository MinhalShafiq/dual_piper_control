#!/bin/bash
# Setup two CAN interfaces for dual piper arm control.
# Usage: sudo bash setup_can.sh
#
# Uses piper_sdk/can_activate.sh with USB addresses to ensure each
# adapter always gets the correct name regardless of plug order.
#
# To find your USB addresses, plug in one adapter at a time and run:
#   sudo ethtool -i can0 | grep bus-info

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================
# CONFIGURATION - Edit these to match your hardware
# ============================================================
# Format: can_activate.sh <name> <bitrate> <usb_address>
CAN0_USB="1-3:1.0"
CAN1_USB="1-2:1.0"
BITRATE=1000000
# ============================================================

echo "========== Dual Piper CAN Setup =========="
echo "  can0 -> USB $CAN0_USB @ ${BITRATE}bps"
echo "  can1 -> USB $CAN1_USB @ ${BITRATE}bps"
echo ""

bash "$SCRIPT_DIR/piper_sdk/can_activate.sh" can0 "$BITRATE" "$CAN0_USB"
echo ""
bash "$SCRIPT_DIR/piper_sdk/can_activate.sh" can1 "$BITRATE" "$CAN1_USB"

echo ""
echo "CAN interfaces configured:"
ip -br link show type can
echo "========== Setup Complete =========="
