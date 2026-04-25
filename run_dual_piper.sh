#!/bin/bash
# ============================================================
# Dual Piper Control - Monitor master/slave arm positions
#
# Both arms must already be configured (bash reset.sh) and
# connected to the SAME CAN bus with slave powered on first.
#
# Usage:
#   bash run_dual_piper.sh
# ============================================================

CAN_PORT="can0"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================"
echo "  Dual Piper Arm Control"
echo "============================================"
echo "  CAN bus: $CAN_PORT"
echo "============================================"
echo ""

if ! ip link show "$CAN_PORT" &>/dev/null; then
    echo "Error: CAN interface '$CAN_PORT' not found."
    echo "Run 'sudo bash setup_can.sh' first."
    exit 1
fi

python3 "$SCRIPT_DIR/dual_piper.py" --can "$CAN_PORT"
