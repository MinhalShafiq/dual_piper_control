#!/usr/bin/env python3
"""
Dual Piper Control - Monitor and maintain master/slave arm operation.

Both arms must be on the SAME CAN bus (one CAN adapter).
One arm configured as master (0xFA), the other as slave (0xFC).

This script:
  1. Enables the slave arm in high-follow mode
  2. Sends the slave to zero position and waits for it to arrive
  3. Monitors joint positions of both arms
  4. Periodically re-sends enable to keep slave responsive

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

# Constants
ENABLE_TIMEOUT = 10
LOOP_RATE = 0.005  # 200Hz


def is_arm_enabled(piper):
    msgs = piper.GetArmLowSpdInfoMsgs()
    return (
        msgs.motor_1.foc_status.driver_enable_status and
        msgs.motor_2.foc_status.driver_enable_status and
        msgs.motor_3.foc_status.driver_enable_status and
        msgs.motor_4.foc_status.driver_enable_status and
        msgs.motor_5.foc_status.driver_enable_status and
        msgs.motor_6.foc_status.driver_enable_status
    )


def print_positions(piper):
    # Master data from control frames
    ctrl = piper.GetArmJointCtrl().joint_ctrl
    # Slave data from feedback frames
    fb = piper.GetArmJointMsgs().joint_state
    fb_grip = piper.GetArmGripperMsgs().gripper_state.grippers_angle

    print(
        f"  Master: "
        f"J1={ctrl.joint_1*0.001:7.2f}  J2={ctrl.joint_2*0.001:7.2f}  "
        f"J3={ctrl.joint_3*0.001:7.2f}  J4={ctrl.joint_4*0.001:7.2f}  "
        f"J5={ctrl.joint_5*0.001:7.2f}  J6={ctrl.joint_6*0.001:7.2f}"
    )
    print(
        f"  Slave:  "
        f"J1={fb.joint_1*0.001:7.2f}  J2={fb.joint_2*0.001:7.2f}  "
        f"J3={fb.joint_3*0.001:7.2f}  J4={fb.joint_4*0.001:7.2f}  "
        f"J5={fb.joint_5*0.001:7.2f}  J6={fb.joint_6*0.001:7.2f}  "
        f"Grip={fb_grip*0.001:.1f}"
    )


def enable_slave(piper):
    """Enable slave arm with high-follow mode for master/slave operation."""
    print("  Enabling slave arm...")
    start = time.time()
    while time.time() - start < ENABLE_TIMEOUT:
        # High-follow mode: 0xAD makes slave track master CAN frames
        piper.MotionCtrl_2(0x01, 0x01, 100, 0xAD)
        piper.EnableArm(7)
        piper.GripperCtrl(0, 1000, 0x01, 0)
        time.sleep(0.5)

        if is_arm_enabled(piper):
            print("  Slave arm enabled (high-follow mode).")
            return True

        enable_list = [
            piper.GetArmLowSpdInfoMsgs().motor_1.foc_status.driver_enable_status,
            piper.GetArmLowSpdInfoMsgs().motor_2.foc_status.driver_enable_status,
            piper.GetArmLowSpdInfoMsgs().motor_3.foc_status.driver_enable_status,
            piper.GetArmLowSpdInfoMsgs().motor_4.foc_status.driver_enable_status,
            piper.GetArmLowSpdInfoMsgs().motor_5.foc_status.driver_enable_status,
            piper.GetArmLowSpdInfoMsgs().motor_6.foc_status.driver_enable_status,
        ]
        print(f"  Enable status: {enable_list}")

    print("  WARNING: Slave enable timed out!")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Dual Piper Control - Master/slave arm monitor and control"
    )
    parser.add_argument(
        "--can", default="can0",
        help="CAN interface (both arms share one bus, default: can0)"
    )
    args = parser.parse_args()

    print("============================================")
    print("  Dual Piper Arm Control")
    print("============================================")
    print(f"  CAN bus: {args.can}")
    print("============================================\n")

    piper = C_PiperInterface_V2(args.can)
    piper.ConnectPort()
    time.sleep(2)

    # Enable slave arm in high-follow mode.
    # Both arms are already on, so don't send zero commands —
    # that would conflict with master's CAN frames and cause jiggling.
    # To start at zero, manually move the master arm to zero before running.
    if not enable_slave(piper):
        print("Failed to enable slave. Check connections and power.")
        piper.DisconnectPort()
        sys.exit(1)

    # Send high-follow mode repeatedly to make sure it sticks
    print("  Activating high-follow mode...")
    for _ in range(20):
        piper.MotionCtrl_2(0x01, 0x01, 100, 0xAD)
        piper.EnableArm(7)
        piper.GripperCtrl(0, 1000, 0x01, 0)
        time.sleep(0.05)

    running = True

    def signal_handler(sig, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("\n=== MIRRORING ACTIVE ===")
    print("Move the master arm - slave follows via CAN.")
    print("Press Ctrl+C to stop.\n")

    loop_count = 0
    try:
        while running:
            loop_count += 1

            # Re-send enable + high-follow every 100 iterations (~0.5s)
            # to prevent slave from losing sync
            if loop_count % 100 == 0:
                piper.MotionCtrl_2(0x01, 0x01, 100, 0xAD)
                piper.EnableArm(7)
                piper.GripperCtrl(0, 1000, 0x01, 0)

            # Print status every ~2 seconds
            if loop_count % 400 == 0:
                print_positions(piper)

            time.sleep(LOOP_RATE)
    except KeyboardInterrupt:
        pass

    print("\n\nDisconnecting...")
    piper.DisconnectPort()
    print("Done.")


if __name__ == "__main__":
    main()
