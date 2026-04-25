#!/bin/bash
# ============================================================
# Configure Piper Arms for Master/Slave Operation
#
# This configures which arm is master and which is slave.
# After running, power cycle both arms:
#   1. Power OFF both arms
#   2. Connect both arms to the SAME CAN adapter
#   3. Power ON the SLAVE arm first
#   4. Power ON the MASTER arm second
#   5. Wait a few seconds - slave will follow master
#
# Usage:
#   bash reset.sh              # configure both arms
#   bash reset.sh master       # configure master only
#   bash reset.sh slave        # configure slave only
# ============================================================

CAN_PORT="can0"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${1:-both}" in
    master)
        echo "Configuring master arm on $CAN_PORT..."
        python3 "$SCRIPT_DIR/reset_arms.py" "$CAN_PORT" master
        ;;
    slave)
        echo "Configuring slave arm on $CAN_PORT..."
        python3 "$SCRIPT_DIR/reset_arms.py" "$CAN_PORT" slave
        ;;
    both)
        echo "=========================================="
        echo "  Dual Piper Arm Configuration"
        echo "=========================================="
        echo ""
        echo "Connect ONE arm at a time to configure it."
        echo ""
        echo "Step 1: Connect the MASTER arm to $CAN_PORT"
        read -p "Press Enter when ready..."
        python3 "$SCRIPT_DIR/reset_arms.py" "$CAN_PORT" master

        echo ""
        echo "Step 2: Disconnect master, connect the SLAVE arm to $CAN_PORT"
        read -p "Press Enter when ready..."
        python3 "$SCRIPT_DIR/reset_arms.py" "$CAN_PORT" slave

        echo ""
        echo "=========================================="
        echo "  Configuration complete!"
        echo ""
        echo "  Now connect BOTH arms to the same CAN adapter:"
        echo "    1. Power OFF both arms"
        echo "    2. Connect both to the CAN adapter"
        echo "    3. Power ON SLAVE arm first"
        echo "    4. Power ON MASTER arm second"
        echo "    5. Wait a few seconds"
        echo "    6. Move master arm - slave will follow"
        echo "=========================================="
        ;;
    *)
        echo "Usage: bash reset.sh [master|slave|both]"
        exit 1
        ;;
esac
