#!/bin/bash
# ============================================================
# Reset Piper Arms - Standalone reset script
#
# Usage:
#   bash reset.sh              # reset both arms
#   bash reset.sh left         # reset left arm only
#   bash reset.sh right        # reset right arm only
# ============================================================

LEFT="can0"
RIGHT="can1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${1:-both}" in
    left)
        echo "Resetting left arm ($LEFT)..."
        python3 "$SCRIPT_DIR/reset_arms.py" --left "$LEFT"
        ;;
    right)
        echo "Resetting right arm ($RIGHT)..."
        python3 "$SCRIPT_DIR/reset_arms.py" --right "$RIGHT"
        ;;
    both)
        echo "Resetting both arms ($LEFT, $RIGHT)..."
        python3 "$SCRIPT_DIR/reset_arms.py" --left "$LEFT" --right "$RIGHT"
        ;;
    *)
        echo "Usage: bash reset.sh [left|right|both]"
        exit 1
        ;;
esac
