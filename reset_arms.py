#!/usr/bin/env python3
"""
Reset a single Piper arm to its zero/home position.

After reset, motors stay enabled holding the zero position.

Usage:
    python3 reset_arms.py can0
    python3 reset_arms.py can1
"""

import sys
import os
import time

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


def reset_arm(can_port, name):
    """Full reset sequence for one arm."""
    print(f"\n--- Resetting {name} ({can_port}) ---")

    # Connect
    print(f"  Connecting to {can_port}...")
    piper = C_PiperInterface_V2(can_port)
    piper.ConnectPort()
    time.sleep(2)

    # Enable
    if not enable_arm(piper, name):
        print(f"  Failed to enable {name}.")
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

    # Move to home
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

    print(f"  {name} holding at zero (motors stay enabled).")
    piper.DisconnectPort()
    print(f"  {name} reset complete.")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 reset_arms.py <can_port> [name]")
        print("  e.g. python3 reset_arms.py can0 Left")
        sys.exit(1)

    can_port = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else can_port

    success = reset_arm(can_port, name)
    sys.exit(0 if success else 1)
