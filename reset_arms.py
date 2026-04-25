#!/usr/bin/env python3
"""
Reset a single Piper arm to its zero/home position.

Enable sequence follows the piper_control library's proven approach:
  1. Resume emergency stop (MotionCtrl_1)
  2. Enable motors individually (1-6)
  3. Set CAN control mode (MotionCtrl_2)
  4. Retry disable->enable if mode doesn't take

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
JOINT_ZERO_THRESHOLD = 500  # 0.5 degrees in 0.001 deg units
RESET_TIMEOUT = 15
HOME_POSITION = [0, 0, 0, 0, 0, 0]
MOVE_SPEED = 50
ENABLE_TIMEOUT = 10.0


def is_arm_enabled(piper):
    """Check if all 6 motors are enabled."""
    msgs = piper.GetArmLowSpdInfoMsgs()
    return (
        msgs.motor_1.foc_status.driver_enable_status and
        msgs.motor_2.foc_status.driver_enable_status and
        msgs.motor_3.foc_status.driver_enable_status and
        msgs.motor_4.foc_status.driver_enable_status and
        msgs.motor_5.foc_status.driver_enable_status and
        msgs.motor_6.foc_status.driver_enable_status
    )


def disable_arm(piper, timeout=ENABLE_TIMEOUT):
    """Disable arm: resume emergency stop and wait for standby."""
    start = time.time()
    while time.time() - start < timeout:
        # Resume from any emergency stop state
        piper.MotionCtrl_1(0x02, 0, 0)
        time.sleep(0.1)

        status = piper.GetArmStatus().arm_status
        # ctrl_mode 0 = standby, arm_status 0 = normal
        if status.ctrl_mode == 0 and status.arm_status == 0:
            return True
        time.sleep(0.5)
    return False


def enable_arm(piper, timeout=ENABLE_TIMEOUT):
    """Enable motors individually (1-6), then set CAN control mode."""
    start = time.time()
    while time.time() - start < timeout:
        # Enable each motor individually (not 7 which also moves gripper)
        for motor in range(1, 7):
            piper.EnableArm(motor)
        time.sleep(0.1)

        if is_arm_enabled(piper):
            # Set CAN command mode + joint control + position/velocity
            piper.MotionCtrl_2(0x01, 0x01, 100, 0x00)
            time.sleep(0.5)
            return True

        time.sleep(0.5)
    return False


def full_reset_enable(piper, name, max_attempts=3):
    """Full disable->enable cycle with retries (piper_control approach)."""
    for attempt in range(1, max_attempts + 1):
        print(f"  {name}: enable attempt {attempt}/{max_attempts}...")

        # Step 1: Disable / clear errors
        print(f"  {name}: clearing errors and resuming...")
        if not disable_arm(piper):
            print(f"  {name}: disable timed out, retrying...")
            continue

        # Step 2: Enable motors
        print(f"  {name}: enabling motors...")
        if not enable_arm(piper):
            print(f"  {name}: enable timed out, retrying...")
            continue

        # Step 3: Verify CAN control mode
        ctrl_mode = piper.GetArmStatus().arm_status.ctrl_mode
        print(f"  {name}: ctrl_mode = {ctrl_mode}")
        if ctrl_mode == 1:
            print(f"  {name}: enabled in CAN control mode.")
            return True

        print(f"  {name}: CAN mode not set, will retry full cycle...")

    print(f"  ERROR: {name} failed to enable after {max_attempts} attempts!")
    return False


def enable_gripper(piper, name):
    """Enable gripper separately."""
    print(f"  {name}: enabling gripper...")
    piper.GripperCtrl(0, 1000, 0x01, 0)
    time.sleep(0.5)


def joints_at_zero(piper):
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
    print(f"\n--- Resetting {name} ({can_port}) ---")

    # Connect
    print(f"  Connecting to {can_port}...")
    piper = C_PiperInterface_V2(can_port)
    piper.ConnectPort()
    time.sleep(2)

    # Full enable sequence with retries
    if not full_reset_enable(piper, name):
        piper.DisconnectPort()
        return False

    enable_gripper(piper, name)

    # Move to zero position
    print(f"  Moving {name} to zero position...")
    print_joint_positions(piper, name)

    start = time.time()
    settled_count = 0

    while time.time() - start < RESET_TIMEOUT:
        piper.MotionCtrl_2(0x01, 0x01, MOVE_SPEED, 0x00)
        piper.JointCtrl(*HOME_POSITION)
        piper.GripperCtrl(0, 1000, 0x01, 0)
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
        piper.MotionCtrl_2(0x01, 0x01, MOVE_SPEED, 0x00)
        piper.JointCtrl(*HOME_POSITION)
        piper.GripperCtrl(0, 1000, 0x01, 0)
        time.sleep(0.005)

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

    try:
        success = reset_arm(can_port, name)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n  ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
