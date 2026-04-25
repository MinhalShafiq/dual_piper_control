#!/bin/bash
# ============================================================
# Reset Piper Arms
#
# Each arm is reset in its own Python process to avoid
# SDK singleton conflicts.
#
# Usage:
#   bash reset.sh              # reset both arms
#   bash reset.sh left         # reset left arm only
#   bash reset.sh right        # reset right arm only
# ============================================================

LEFT="can0"
RIGHT="can1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

reset_one() {
    local port=$1
    local name=$2
    echo "========== Resetting $name ($port) =========="
    python3 "$SCRIPT_DIR/reset_arms.py" "$port" "$name"
    local rc=$?
    echo ""
    return $rc
}

case "${1:-both}" in
    left)
        reset_one "$LEFT" "Left"
        ;;
    right)
        reset_one "$RIGHT" "Right"
        ;;
    both)
        reset_one "$LEFT" "Left"
        rc1=$?
        reset_one "$RIGHT" "Right"
        rc2=$?
        if [ $rc1 -ne 0 ] || [ $rc2 -ne 0 ]; then
            echo "Some arms failed to reset."
            exit 1
        fi
        echo "Both arms reset successfully."
        ;;
    *)
        echo "Usage: bash reset.sh [left|right|both]"
        exit 1
        ;;
esac
