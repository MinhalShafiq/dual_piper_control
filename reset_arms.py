#!/usr/bin/env python3
"""
Reset a single Piper arm to its zero/home position.

Uses piper_control library for reliable enable/reset sequence.

Usage:
    python3 reset_arms.py can0
    python3 reset_arms.py can1
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from piper_control import piper_interface, piper_init

# Constants
JOINT_ZERO_THRESHOLD = 500  # 0.5 degrees in 0.001 deg units
RESET_TIMEOUT = 15
HOME_POSITION = [0, 0, 0, 0, 0, 0]
MOVE_SPEED = 50


def joints_at_zero(robot):
    joints = robot.piper.GetArmJointMsgs().joint_state
    return (
        abs(joints.joint_1) < JOINT_ZERO_THRESHOLD and
        abs(joints.joint_2) < JOINT_ZERO_THRESHOLD and
        abs(joints.joint_3) < JOINT_ZERO_THRESHOLD and
        abs(joints.joint_4) < JOINT_ZERO_THRESHOLD and
        abs(joints.joint_5) < JOINT_ZERO_THRESHOLD and
        abs(joints.joint_6) < JOINT_ZERO_THRESHOLD
    )


def print_joint_positions(robot, name):
    joints = robot.piper.GetArmJointMsgs().joint_state
    gripper = robot.piper.GetArmGripperMsgs().gripper_state.grippers_angle
    print(
        f"  {name} joints (deg): "
        f"J1={joints.joint_1 * 0.001:7.2f}  J2={joints.joint_2 * 0.001:7.2f}  "
        f"J3={joints.joint_3 * 0.001:7.2f}  J4={joints.joint_4 * 0.001:7.2f}  "
        f"J5={joints.joint_5 * 0.001:7.2f}  J6={joints.joint_6 * 0.001:7.2f}  "
        f"Grip={gripper * 0.001:.1f}"
    )


def reset_arm(can_port, name):
    print(f"\n--- Resetting {name} ({can_port}) ---")

    # Connect using piper_control
    print(f"  Connecting to {can_port}...")
    robot = piper_interface.PiperInterface(can_port=can_port)
    time.sleep(1)

    # Reset arm: disable -> enable -> set CAN control mode
    # This handles the full sequence including emergency stop resume
    print(f"  Resetting and enabling {name}...")
    piper_init.reset_arm(
        robot,
        arm_controller=piper_interface.ArmController.POSITION_VELOCITY,
        move_mode=piper_interface.MoveMode.JOINT,
        timeout_seconds=15.0,
    )
    piper_init.reset_gripper(robot, timeout_seconds=10.0)
    print(f"  {name} enabled in CAN control mode.")

    # Move to zero position
    print(f"  Moving {name} to zero position...")
    print_joint_positions(robot, name)

    start = time.time()
    settled_count = 0

    while time.time() - start < RESET_TIMEOUT:
        robot.piper.MotionCtrl_2(0x01, 0x01, MOVE_SPEED, 0x00)
        robot.piper.JointCtrl(*HOME_POSITION)
        robot.piper.GripperCtrl(0, 1000, 0x01, 0)
        time.sleep(0.005)

        motion_done = robot.piper.GetArmStatus().arm_status.motion_status == 0
        at_zero = joints_at_zero(robot)

        if motion_done and at_zero:
            settled_count += 1
            if settled_count >= 10:
                break
        else:
            settled_count = 0

    # Hold at zero to stabilize
    print(f"  Holding {name} at zero to stabilize...")
    for _ in range(200):
        robot.piper.MotionCtrl_2(0x01, 0x01, MOVE_SPEED, 0x00)
        robot.piper.JointCtrl(*HOME_POSITION)
        robot.piper.GripperCtrl(0, 1000, 0x01, 0)
        time.sleep(0.005)

    print_joint_positions(robot, name)

    # Keep motors enabled (don't disable - arm would sag)
    print(f"  {name} holding at zero (motors stay enabled).")
    robot.piper.DisconnectPort()
    print(f"  {name} reset complete.")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 reset_arms.py <can_port> [name]")
        print("  e.g. python3 reset_arms.py can0 Left")
        sys.exit(1)

    can_port = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else can_port

    try:
        success = reset_arm(can_port, name)
        sys.exit(0 if success else 1)
    except TimeoutError as e:
        print(f"\n  ERROR: {e}")
        print("  Arm may need a power cycle. Check CAN cables and power.")
        sys.exit(1)
    except Exception as e:
        print(f"\n  ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
