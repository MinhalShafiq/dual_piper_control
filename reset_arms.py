#!/usr/bin/env python3
"""
Configure and reset a Piper arm for dual-arm master/slave operation.

The official dual Piper approach:
  - Both arms share ONE CAN bus (single CAN adapter)
  - One arm is configured as master (0xFA), the other as slave (0xFC)
  - Power slave first, then master
  - Master arm movements are replicated to slave via CAN protocol

This script configures an arm's role (master/slave) and optionally resets it.

Usage:
    python3 reset_arms.py can0 master    # Configure arm on can0 as master
    python3 reset_arms.py can0 slave     # Configure arm on can0 as slave
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from piper_sdk import C_PiperInterface_V2


def configure_arm(can_port, role):
    """Configure arm as master (0xFA) or slave (0xFC)."""
    print(f"Connecting to {can_port}...")
    piper = C_PiperInterface_V2(can_port)
    piper.ConnectPort()
    time.sleep(1)

    if role == "master":
        print(f"  Setting arm on {can_port} as MASTER (0xFA)...")
        piper.MasterSlaveConfig(0xFA, 0, 0, 0)
    elif role == "slave":
        print(f"  Setting arm on {can_port} as SLAVE (0xFC)...")
        piper.MasterSlaveConfig(0xFC, 0, 0, 0)
    else:
        print(f"  ERROR: Unknown role '{role}'. Use 'master' or 'slave'.")
        piper.DisconnectPort()
        return False

    time.sleep(0.5)

    # Configure gripper parameters (saved on the arm, needed for gripper
    # feedback and control to work). Without this the gripper has no data.
    print(f"  Setting gripper parameters (range=100%, max=70mm)...")
    piper.GripperTeachingPendantParamConfig(100, 70)

    time.sleep(1)
    print(f"  Configuration sent. Power cycle the arm for it to take effect.")
    piper.DisconnectPort()
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 reset_arms.py <can_port> <master|slave>")
        print("")
        print("Examples:")
        print("  python3 reset_arms.py can0 master   # Set arm as master")
        print("  python3 reset_arms.py can0 slave    # Set arm as slave")
        sys.exit(1)

    can_port = sys.argv[1]
    role = sys.argv[2].lower()

    try:
        success = configure_arm(can_port, role)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n  ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
