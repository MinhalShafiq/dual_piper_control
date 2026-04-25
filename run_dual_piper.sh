#!/bin/bash
# ============================================================
# Dual Piper Control - Launcher Script
#
# Usage:
#   bash run_dual_piper.sh
#
# Change MASTER and SLAVE below to swap which arm leads.
# ============================================================

# CONFIGURATION - Change these to swap master/slave
MASTER="can_left"
SLAVE="can_right"

# ============================================================
# You shouldn't need to edit below this line
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================"
echo "  Dual Piper Arm Control"
echo "============================================"
echo "  Master arm: $MASTER"
echo "  Slave arm:  $SLAVE"
echo "============================================"
echo ""

# Check if CAN interfaces exist
if ! ip link show "$MASTER" &>/dev/null; then
    echo "Error: CAN interface '$MASTER' not found."
    echo "Run 'sudo bash setup_can.sh' first to configure CAN interfaces."
    echo ""
    echo "Available CAN interfaces:"
    ip -br link show type can 2>/dev/null || echo "  (none found)"
    exit 1
fi

if ! ip link show "$SLAVE" &>/dev/null; then
    echo "Error: CAN interface '$SLAVE' not found."
    echo "Run 'sudo bash setup_can.sh' first to configure CAN interfaces."
    echo ""
    echo "Available CAN interfaces:"
    ip -br link show type can 2>/dev/null || echo "  (none found)"
    exit 1
fi

echo "CAN interfaces found."
echo ""

# Step 1: Reset both arms to zero position
echo "Step 1: Resetting both arms to zero..."
python3 "$SCRIPT_DIR/reset_arms.py" --left "$MASTER" --right "$SLAVE"
if [ $? -ne 0 ]; then
    echo "Error: Reset failed. Exiting."
    exit 1
fi

echo ""

# Step 2: Start mirroring
echo "Step 2: Starting mirroring..."
python3 "$SCRIPT_DIR/dual_piper.py" --master "$MASTER" --slave "$SLAVE"
