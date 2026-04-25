#!/usr/bin/env python3
"""
Dual Piper Control - Read master/slave arm data from a shared CAN bus.

Both arms must be on the SAME CAN bus (one CAN adapter).
Master arm is in teach mode (move by hand), slave follows via hardware.

This script monitors and prints the joint positions of both arms.
The actual master->slave replication happens at the CAN hardware level.

To control the slave independently (e.g. move to zero), the master
must be physically disconnected from the CAN bus first.

Usage:
    python3 dual_piper.py --can can0
"""

import sys
import os
import time
import signal
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from piper_sdk import C_PiperInterface_V2


def print_status(piper):
    """Print master (ctrl) and slave (feedback) joint data."""
    # Master arm data comes from control messages (GetArmJointCtrl)
    ctrl = piper.GetArmJointCtrl()
    ctrl_grip = piper.GetArmGripperCtrl()

    # Slave arm data comes from feedback messages (GetArmJointMsgs)
    fb = piper.GetArmJointMsgs().joint_state
    fb_grip = piper.GetArmGripperMsgs().gripper_state.grippers_angle

    print(
        f"  Master: J1={ctrl.joint_state.joint_1*0.001:7.2f} "
        f"J2={ctrl.joint_state.joint_2*0.001:7.2f} "
        f"J3={ctrl.joint_state.joint_3*0.001:7.2f} "
        f"J4={ctrl.joint_state.joint_4*0.001:7.2f} "
        f"J5={ctrl.joint_state.joint_5*0.001:7.2f} "
        f"J6={ctrl.joint_state.joint_6*0.001:7.2f}"
    )
    print(
        f"  Slave:  J1={fb.joint_1*0.001:7.2f} "
        f"J2={fb.joint_2*0.001:7.2f} "
        f"J3={fb.joint_3*0.001:7.2f} "
        f"J4={fb.joint_4*0.001:7.2f} "
        f"J5={fb.joint_5*0.001:7.2f} "
        f"J6={fb.joint_6*0.001:7.2f}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Dual Piper Monitor - Watch master/slave arm positions"
    )
    parser.add_argument(
        "--can", default="can0",
        help="CAN interface (both arms share one bus, default: can0)"
    )
    args = parser.parse_args()

    print("============================================")
    print("  Dual Piper Arm Monitor")
    print("============================================")
    print(f"  CAN bus: {args.can}")
    print("============================================")
    print("")

    piper = C_PiperInterface_V2(args.can)
    piper.ConnectPort()
    time.sleep(1)

    running = True

    def signal_handler(sig, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=== MONITORING ===")
    print("Move the master arm - slave follows via CAN hardware.")
    print("Press Ctrl+C to stop.\n")

    try:
        while running:
            print_status(piper)
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass

    print("\nDisconnecting...")
    piper.DisconnectPort()
    print("Done.")


if __name__ == "__main__":
    main()
