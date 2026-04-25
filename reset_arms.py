#!/usr/bin/env python3
"""
Reset both Piper arms to their zero/home position.

Can be run at any time to bring both arms back to zero.
After reset, motors are disabled and the arms will be limp.

Usage:
    python3 reset_arms.py --left can_left --right can_right
    python3 reset_arms.py --left can_left               # reset only left
    python3 reset_arms.py --right can_right              # reset only right
"""

import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from piper_sdk import C_PiperInterface_V2

# Constants
CAN_CTRL_MODE = 0x01
JOINT_CTRL_MODE = 0x01
RESET_SPEED = 50
VEL_MODE = 0x00
ENABLE_MOTORS = 7
GRIPPER_EFFORT = 1000
GRIPPER_CODE = 0x01
ENABLE_TIMEOUT = 10
RESET_TIMEOUT = 15
JOINT_ZERO_THRESHOLD = 500  # 0.5 degrees in 0.001 deg units
HOME_POSITION = [0, 0, 0, 0, 0, 0]


def enable_arm(piper, name):
    """Enable all motors on an arm. Returns True on success."""
    print(f"  Enabling {name}...")
    piper.EnableArm(ENABLE_MOTORS)
    piper.GripperCtrl(0, GRIPPER_EFFORT, GRIPPER_CODE, 0)
    time.sleep(0.5)

    start = time.time()
    while time.time() - start < ENABLE_TIMEOUT:
        enable_list = [
            piper.GetArmLowSpdInfoMsgs().motor_1.foc_status.driver_enable_status,
            piper.GetArmLowSpdInfoMsgs().motor_2.foc_status.driver_enable_status,
            piper.GetArmLowSpdInfoMsgs().motor_3.foc_status.driver_enable_status,
            piper.GetArmLowSpdInfoMsgs().motor_4.foc_status.driver_enable_status,
            piper.GetArmLowSpdInfoMsgs().motor_5.foc_status.driver_enable_status,
            piper.GetArmLowSpdInfoMsgs().motor_6.foc_status.driver_enable_status,
        ]
        if all(enable_list):
            print(f"  {name} enabled.")
            return True
        print(f"  {name} enable status: {enable_list}")
        piper.EnableArm(ENABLE_MOTORS)
        piper.GripperCtrl(0, GRIPPER_EFFORT, GRIPPER_CODE, 0)
        time.sleep(0.5)

    print(f"  ERROR: {name} enable timed out!")
    return False


def joints_at_zero(piper):
    """Check if all joints are within threshold of zero."""
    joints = piper.GetArmJointMsgs().joint_state
    return (
        abs(joints.joint_1) < JOINT_ZERO_THRESHOLD and
        abs(joints.joint_2) < JOINT_ZERO_THRESHOLD and
        abs(joints.joint_3) < JOINT_ZERO_THRESHOLD and
        abs(joints.joint_4) < JOINT_ZERO_THRESHOLD and
        abs(joints.joint_5) < JOINT_ZERO_THRESHOLD and
        abs(joints.joint_6) < JOINT_ZERO_THRESHOLD
    )


def print_joint_positions(piper, name):
    """Print current joint positions."""
    joints = piper.GetArmJointMsgs().joint_state
    gripper = piper.GetArmGripperMsgs().gripper_state.grippers_angle
    print(
        f"  {name} joints (deg): "
        f"J1={joints.joint_1 * 0.001:7.2f}  J2={joints.joint_2 * 0.001:7.2f}  "
        f"J3={joints.joint_3 * 0.001:7.2f}  J4={joints.joint_4 * 0.001:7.2f}  "
        f"J5={joints.joint_5 * 0.001:7.2f}  J6={joints.joint_6 * 0.001:7.2f}  "
        f"Grip={gripper * 0.001:.1f}"
    )


def reset_single_arm(can_port, name):
    """Full reset sequence for one arm: connect, enable, move to zero, disable."""
    print(f"\n--- Resetting {name} ({can_port}) ---")

    # Connect
    print(f"  Connecting to {can_port}...")
    piper = C_PiperInterface_V2(can_port)
    piper.ConnectPort()
    time.sleep(2)

    # Enable (matching the working demo pattern: EnableArm -> loop check)
    if not enable_arm(piper, name):
        print(f"  Failed to enable {name}. Disconnecting.")
        piper.DisconnectPort()
        return False

    # Set CAN + joint control mode and wait for it to take effect
    print(f"  Setting {name} to CAN joint control mode...")
    start = time.time()
    while time.time() - start < ENABLE_TIMEOUT:
        piper.MotionCtrl_2(CAN_CTRL_MODE, JOINT_CTRL_MODE, RESET_SPEED, VEL_MODE)
        time.sleep(0.5)
        ctrl_mode = piper.GetArmStatus().arm_status.ctrl_mode
        print(f"  {name} ctrl_mode: {ctrl_mode}")
        if ctrl_mode == CAN_CTRL_MODE:
            break
    print(f"  {name} in CAN control mode.")

    # Move to home - send EnableArm + MotionCtrl_2 + JointCtrl every iteration
    # (matching the working piper_joint_ctrl.py demo pattern)
    print(f"  Moving {name} to zero position...")
    print_joint_positions(piper, name)
    start = time.time()
    settled_count = 0

    while time.time() - start < RESET_TIMEOUT:
        piper.EnableArm(ENABLE_MOTORS)
        piper.MotionCtrl_2(CAN_CTRL_MODE, JOINT_CTRL_MODE, RESET_SPEED, VEL_MODE)
        piper.JointCtrl(*HOME_POSITION)
        piper.GripperCtrl(0, GRIPPER_EFFORT, GRIPPER_CODE, 0)
        time.sleep(0.005)

        motion_done = piper.GetArmStatus().arm_status.motion_status == 0
        at_zero = joints_at_zero(piper)

        if motion_done and at_zero:
            settled_count += 1
            if settled_count >= 10:
                break
        else:
            settled_count = 0

    # Hold at zero to stabilize
    print(f"  Holding {name} at zero to stabilize...")
    for _ in range(200):
        piper.EnableArm(ENABLE_MOTORS)
        piper.MotionCtrl_2(CAN_CTRL_MODE, JOINT_CTRL_MODE, RESET_SPEED, VEL_MODE)
        piper.JointCtrl(*HOME_POSITION)
        piper.GripperCtrl(0, GRIPPER_EFFORT, GRIPPER_CODE, 0)
        time.sleep(0.005)

    # Final check
    print_joint_positions(piper, name)

    if not joints_at_zero(piper):
        print(f"  WARNING: {name} not exactly at zero. Sending correction...")
        for _ in range(400):
            piper.EnableArm(ENABLE_MOTORS)
            piper.MotionCtrl_2(CAN_CTRL_MODE, JOINT_CTRL_MODE, 20, VEL_MODE)
            piper.JointCtrl(*HOME_POSITION)
            piper.GripperCtrl(0, GRIPPER_EFFORT, GRIPPER_CODE, 0)
            time.sleep(0.005)
        time.sleep(1.0)
        print_joint_positions(piper, name)

    # Keep motors enabled and holding zero position.
    # Do NOT disable — the arm would go limp and sag under gravity.
    # Just disconnect the SDK (CAN bus closes but arm holds last command).
    print(f"  {name} holding at zero (motors stay enabled).")
    piper.DisconnectPort()

    print(f"  {name} reset complete.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Reset Piper arms to zero/home position"
    )
    parser.add_argument(
        "--left", default=None,
        help="CAN interface for the left arm (e.g. can_left)"
    )
    parser.add_argument(
        "--right", default=None,
        help="CAN interface for the right arm (e.g. can_right)"
    )
    args = parser.parse_args()

    if not args.left and not args.right:
        parser.error("Provide at least one arm: --left and/or --right")

    print("============================================")
    print("  Piper Arm Reset")
    print("============================================")

    success = True

    if args.left:
        if not reset_single_arm(args.left, "Left"):
            success = False

    if args.right:
        if not reset_single_arm(args.right, "Right"):
            success = False

    print("")
    if success:
        print("All arms reset to zero position successfully.")
    else:
        print("Some arms failed to reset. Check output above.")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
