#!/usr/bin/env python3
"""
Dual Piper Control - Replicate movement from master arm to slave arm.

The master arm is set to teach mode (free to move by hand).
The slave arm mirrors the master's joint positions in real-time.

Usage:
    python3 dual_piper.py --master can_left --slave can_right
    python3 dual_piper.py --master can_right --slave can_left
"""

import sys
import os
import time
import signal
import argparse

# Add parent dir so piper_sdk can be imported as a package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from piper_sdk import C_PiperInterface_V2


# Constants
JOINT_CTRL_MODE = 0x01      # Joint angle control mode
CAN_CTRL_MODE = 0x01        # CAN command control
TEACH_MODE = 0x00           # Teach/freedrive mode
MOVE_SPEED = 100            # Movement speed (0-100)
VEL_MODE = 0x00             # Velocity mode
ENABLE_MOTORS = 7           # Enable all 6 motors + gripper
GRIPPER_EFFORT = 1000       # Gripper force
GRIPPER_CODE = 0x01         # Standard gripper
LOOP_RATE = 0.005           # 200Hz control loop (5ms)
HOME_POSITION = [0, 0, 0, 0, 0, 0]  # Joint angles in 0.001 degrees
ENABLE_TIMEOUT = 10         # Seconds to wait for arm enable
RESET_SPEED = 50            # Slower speed for reset to avoid overshoot
RESET_TIMEOUT = 15          # Max seconds to wait for reset to complete
JOINT_ZERO_THRESHOLD = 500  # 0.5 degrees tolerance (in 0.001 deg units)


class DualPiperController:
    def __init__(self, master_can, slave_can):
        self.master_can = master_can
        self.slave_can = slave_can
        self.master = None
        self.slave = None
        self.running = False

    def connect(self):
        """Connect to both arms."""
        print(f"Connecting to master arm on {self.master_can}...")
        self.master = C_PiperInterface_V2(self.master_can)
        self.master.ConnectPort()
        print(f"  Master connected.")

        print(f"Connecting to slave arm on {self.slave_can}...")
        self.slave = C_PiperInterface_V2(self.slave_can)
        self.slave.ConnectPort()
        print(f"  Slave connected.")

        # Wait for CAN bus to start receiving feedback data
        print("  Waiting for CAN feedback...")
        time.sleep(2)

    def _wait_enable(self, piper, name):
        """Wait for all motors to report enabled status."""
        print(f"  Enabling {name}...")
        # Send initial enable command
        piper.EnableArm(ENABLE_MOTORS)
        piper.GripperCtrl(0, GRIPPER_EFFORT, GRIPPER_CODE, 0)
        time.sleep(0.5)

        start = time.time()
        while time.time() - start < ENABLE_TIMEOUT:
            enable_list = []
            enable_list.append(piper.GetArmLowSpdInfoMsgs().motor_1.foc_status.driver_enable_status)
            enable_list.append(piper.GetArmLowSpdInfoMsgs().motor_2.foc_status.driver_enable_status)
            enable_list.append(piper.GetArmLowSpdInfoMsgs().motor_3.foc_status.driver_enable_status)
            enable_list.append(piper.GetArmLowSpdInfoMsgs().motor_4.foc_status.driver_enable_status)
            enable_list.append(piper.GetArmLowSpdInfoMsgs().motor_5.foc_status.driver_enable_status)
            enable_list.append(piper.GetArmLowSpdInfoMsgs().motor_6.foc_status.driver_enable_status)
            if all(enable_list):
                print(f"  {name} enabled.")
                return True
            print(f"  {name} enable status: {enable_list}")
            piper.EnableArm(ENABLE_MOTORS)
            piper.GripperCtrl(0, GRIPPER_EFFORT, GRIPPER_CODE, 0)
            time.sleep(0.5)
        print(f"  ERROR: {name} enable timed out!")
        return False

    def _joints_at_zero(self, piper):
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

    def _print_joint_positions(self, piper, name):
        """Print current joint positions for debugging."""
        joints = piper.GetArmJointMsgs().joint_state
        gripper = piper.GetArmGripperMsgs().gripper_state.grippers_angle
        print(
            f"  {name} joints (deg): "
            f"J1={joints.joint_1 * 0.001:7.2f}  J2={joints.joint_2 * 0.001:7.2f}  "
            f"J3={joints.joint_3 * 0.001:7.2f}  J4={joints.joint_4 * 0.001:7.2f}  "
            f"J5={joints.joint_5 * 0.001:7.2f}  J6={joints.joint_6 * 0.001:7.2f}  "
            f"Grip={gripper * 0.001:.1f}"
        )

    def _move_to_home(self, piper, name):
        """Move arm to home (zero) position with repeated commands and verification."""
        print(f"  Moving {name} to home position...")

        # Use slower speed for reset to avoid overshoot
        piper.MotionCtrl_2(CAN_CTRL_MODE, JOINT_CTRL_MODE, RESET_SPEED, VEL_MODE)
        time.sleep(0.1)

        start = time.time()
        settled_count = 0

        while time.time() - start < RESET_TIMEOUT:
            # Keep sending home command repeatedly to ensure it's received
            piper.MotionCtrl_2(CAN_CTRL_MODE, JOINT_CTRL_MODE, RESET_SPEED, VEL_MODE)
            piper.JointCtrl(*HOME_POSITION)
            piper.GripperCtrl(0, GRIPPER_EFFORT, GRIPPER_CODE, 0)

            time.sleep(0.1)

            motion_done = piper.GetArmStatus().arm_status.motion_status == 0
            at_zero = self._joints_at_zero(piper)

            if motion_done and at_zero:
                settled_count += 1
                # Require multiple consecutive reads confirming zero to avoid
                # catching a transient moment mid-movement
                if settled_count >= 5:
                    break
            else:
                settled_count = 0

        # Final verification
        self._print_joint_positions(piper, name)

        if not self._joints_at_zero(piper):
            print(f"  WARNING: {name} may not be exactly at zero. Sending final correction...")
            # One more round of commands at very low speed
            for _ in range(20):
                piper.MotionCtrl_2(CAN_CTRL_MODE, JOINT_CTRL_MODE, 20, VEL_MODE)
                piper.JointCtrl(*HOME_POSITION)
                piper.GripperCtrl(0, GRIPPER_EFFORT, GRIPPER_CODE, 0)
                time.sleep(0.1)
            time.sleep(1.0)
            self._print_joint_positions(piper, name)

        print(f"  {name} at home position.")

    def reset_arms(self):
        """Enable and reset both arms to home position."""
        print("\n--- Resetting arms to home position ---")

        # Enable slave first, then master
        self.slave.EnableArm(ENABLE_MOTORS)
        self.master.EnableArm(ENABLE_MOTORS)

        if not self._wait_enable(self.slave, "Slave"):
            return False
        if not self._wait_enable(self.master, "Master"):
            return False

        # Move both to home - slave first so it's ready
        self._move_to_home(self.slave, "Slave")
        self._move_to_home(self.master, "Master")

        # Hold both arms at zero for a moment to let them fully settle.
        # This prevents the drift/rotation that can happen if we release
        # control too quickly after the move completes.
        print("  Holding at zero to stabilize...")
        for _ in range(30):
            self.slave.MotionCtrl_2(CAN_CTRL_MODE, JOINT_CTRL_MODE, RESET_SPEED, VEL_MODE)
            self.slave.JointCtrl(*HOME_POSITION)
            self.slave.GripperCtrl(0, GRIPPER_EFFORT, GRIPPER_CODE, 0)
            self.master.MotionCtrl_2(CAN_CTRL_MODE, JOINT_CTRL_MODE, RESET_SPEED, VEL_MODE)
            self.master.JointCtrl(*HOME_POSITION)
            self.master.GripperCtrl(0, GRIPPER_EFFORT, GRIPPER_CODE, 0)
            time.sleep(0.1)

        # Final position check
        self._print_joint_positions(self.master, "Master")
        self._print_joint_positions(self.slave, "Slave")

        print("--- Both arms at home position ---\n")
        return True

    def _read_master_joints(self):
        """Read current joint angles from master arm (in 0.001 degrees)."""
        joints = self.master.GetArmJointMsgs().joint_state
        return [
            joints.joint_1, joints.joint_2, joints.joint_3,
            joints.joint_4, joints.joint_5, joints.joint_6
        ]

    def _read_master_gripper(self):
        """Read current gripper angle from master arm."""
        return self.master.GetArmGripperMsgs().gripper_state.grippers_angle

    def start_mirroring(self):
        """Main loop: read master joints, send to slave."""
        print("Setting master arm to TEACH mode (free to move by hand)...")
        self.master.MotionCtrl_2(TEACH_MODE, JOINT_CTRL_MODE, 0, VEL_MODE)
        # Disable master so it can be moved freely
        self.master.DisableArm(ENABLE_MOTORS)
        time.sleep(0.5)

        print("Setting slave arm to CAN control mode...")
        self.slave.MotionCtrl_2(CAN_CTRL_MODE, JOINT_CTRL_MODE, MOVE_SPEED, VEL_MODE)
        time.sleep(0.5)

        print("\n=== MIRRORING ACTIVE ===")
        print("Move the master arm - the slave will follow.")
        print("Press Ctrl+C to stop.\n")

        self.running = True
        loop_count = 0

        while self.running:
            # Read master state
            joints = self._read_master_joints()
            gripper = self._read_master_gripper()

            # Send to slave
            self.slave.MotionCtrl_2(CAN_CTRL_MODE, JOINT_CTRL_MODE, MOVE_SPEED, VEL_MODE)
            self.slave.JointCtrl(*joints)
            self.slave.GripperCtrl(abs(gripper), GRIPPER_EFFORT, GRIPPER_CODE, 0)

            # Print status periodically (every ~1 second)
            loop_count += 1
            if loop_count % 200 == 0:
                joint_deg = [j * 0.001 for j in joints]
                print(
                    f"  J1={joint_deg[0]:7.2f}  J2={joint_deg[1]:7.2f}  "
                    f"J3={joint_deg[2]:7.2f}  J4={joint_deg[3]:7.2f}  "
                    f"J5={joint_deg[4]:7.2f}  J6={joint_deg[5]:7.2f}  "
                    f"Gripper={gripper * 0.001:.1f}"
                )

            time.sleep(LOOP_RATE)

    def stop(self):
        """Stop mirroring and disable arms safely."""
        if not self.running and not self.master and not self.slave:
            return
        self.running = False
        print("\n\n=== STOPPING ===")

        if self.slave:
            print("Disabling slave arm...")
            try:
                self.slave.DisableArm(ENABLE_MOTORS)
            except Exception as e:
                print(f"  Warning: {e}")

        if self.master:
            print("Disabling master arm...")
            try:
                self.master.DisableArm(ENABLE_MOTORS)
            except Exception as e:
                print(f"  Warning: {e}")

        print("Arms disabled.")

    def disconnect(self):
        """Disconnect from both arms."""
        if self.master:
            try:
                self.master.DisconnectPort()
            except Exception:
                pass
            self.master = None
        if self.slave:
            try:
                self.slave.DisconnectPort()
            except Exception:
                pass
            self.slave = None


def main():
    parser = argparse.ArgumentParser(
        description="Dual Piper Control - Mirror master arm movements to slave arm"
    )
    parser.add_argument(
        "--master", required=True,
        help="CAN interface for the master arm (e.g. can_left, can0)"
    )
    parser.add_argument(
        "--slave", required=True,
        help="CAN interface for the slave arm (e.g. can_right, can1)"
    )
    args = parser.parse_args()

    controller = DualPiperController(args.master, args.slave)

    def signal_handler(sig, frame):
        controller.stop()
        controller.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        controller.connect()
        if not controller.reset_arms():
            print("Failed to reset arms. Exiting.")
            controller.stop()
            controller.disconnect()
            sys.exit(1)
        controller.start_mirroring()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        controller.stop()
        controller.disconnect()


if __name__ == "__main__":
    main()
