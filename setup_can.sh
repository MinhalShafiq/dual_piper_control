#!/bin/bash
# Setup two CAN interfaces for dual piper arm control.
# Usage: sudo bash setup_can.sh
#
# This script configures two CAN interfaces (one per arm).
# Edit the USB_PORTS below to match your hardware setup.
# To find your USB addresses, plug in one CAN adapter at a time and run:
#   sudo ethtool -i can0 | grep bus-info

set -e

# ============================================================
# CONFIGURATION - Edit these to match your hardware
# ============================================================
# Format: USB_PORTS["bus-info"]="can_name:bitrate"
# Find bus-info by running: sudo ethtool -i can0 | grep bus-info
declare -A USB_PORTS
USB_PORTS["1-2:1.0"]="can0:1000000"
USB_PORTS["1-3:1.0"]="can1:1000000"

EXPECTED_CAN_COUNT=${#USB_PORTS[@]}
# ============================================================

echo "========== Dual Piper CAN Setup =========="

# Check prerequisites
if ! command -v ethtool &> /dev/null; then
    echo "Error: ethtool not installed. Run: sudo apt install ethtool"
    exit 1
fi

if ! command -v cansend &> /dev/null; then
    echo "Error: can-utils not installed. Run: sudo apt install can-utils"
    exit 1
fi

echo "Prerequisites OK (ethtool, can-utils installed)"

# Load gs_usb kernel module
sudo modprobe gs_usb 2>/dev/null || true

# Get current CAN count
CURRENT_CAN_COUNT=$(ip link show type can 2>/dev/null | grep -c "link/can" || echo "0")

if [ "$CURRENT_CAN_COUNT" -lt "$EXPECTED_CAN_COUNT" ]; then
    echo "Error: Found $CURRENT_CAN_COUNT CAN interface(s), expected $EXPECTED_CAN_COUNT."
    echo "Make sure both CAN adapters are plugged in."
    # Show what's currently detected
    for iface in $(ip -br link show type can 2>/dev/null | awk '{print $1}'); do
        BUS_INFO=$(sudo ethtool -i "$iface" 2>/dev/null | grep "bus-info" | awk '{print $2}')
        echo "  Found: $iface at USB port $BUS_INFO"
    done
    exit 1
fi

echo "Found $CURRENT_CAN_COUNT CAN interface(s), configuring..."

# Configure each CAN interface
for iface in $(ip -br link show type can | awk '{print $1}'); do
    BUS_INFO=$(sudo ethtool -i "$iface" | grep "bus-info" | awk '{print $2}')

    if [ -z "$BUS_INFO" ]; then
        echo "Warning: Could not get bus-info for $iface, skipping."
        continue
    fi

    if [ -z "${USB_PORTS[$BUS_INFO]}" ]; then
        echo "Warning: Unknown USB port $BUS_INFO for interface $iface, skipping."
        continue
    fi

    IFS=':' read -r TARGET_NAME TARGET_BITRATE <<< "${USB_PORTS[$BUS_INFO]}"

    echo "  Configuring $iface (USB: $BUS_INFO) -> $TARGET_NAME @ ${TARGET_BITRATE}bps"

    # Bring down, set bitrate, bring up
    sudo ip link set "$iface" down 2>/dev/null || true
    sudo ip link set "$iface" type can bitrate "$TARGET_BITRATE"
    sudo ip link set "$iface" up

    # Rename if needed
    if [ "$iface" != "$TARGET_NAME" ]; then
        sudo ip link set "$iface" down
        sudo ip link set "$iface" name "$TARGET_NAME"
        sudo ip link set "$TARGET_NAME" up
        echo "  Renamed $iface -> $TARGET_NAME"
    fi
done

echo ""
echo "CAN interfaces configured:"
ip -br link show type can
echo "========== Setup Complete =========="
