#!/usr/bin/env python3
"""
Dual Piper Control - Replicate movement from master arm to slave arm.

The master arm is set to teach mode (free to move by hand).
The slave arm mirrors the master's joint positions in real-time.

Run reset_arms.py first to bring both arms to zero position.

Usage:
    python3 dual_piper.py --master can_left --slave can_right
    python3 dual_piper.py --master can_right --slave can_left
"""

import sys
import os
import time
import signal
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from piper_sdk import C_PiperInterface_V2


# Constants
CAN_CTRL_MODE = 0x01
JOINT_CTRL_MODE = 0x01
MOVE_SPEED = 100
VEL_MODE = 0x00
ENABLE_MOTORS = 7
GRIPPER_EFFORT = 1000
GRIPPER_CODE = 0x01
LOOP_RATE = 0.005           # 200Hz control loop
ENABLE_TIMEOUT = 10


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

    def _enable_arm(self, piper, name):
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

    def setup(self):
        """Enable slave arm for CAN control, set master to teach mode."""
        print("\n--- Setting up arms ---")

        # Enable slave arm and set to CAN joint control mode
        if not self._enable_arm(self.slave, "Slave"):
            return False
        self.slave.MotionCtrl_2(CAN_CTRL_MODE, JOINT_CTRL_MODE, MOVE_SPEED, VEL_MODE)
        time.sleep(0.5)
        print("  Slave in CAN joint control mode.")

        # Set master to teach mode (disable motors so it can be moved by hand)
        print("  Setting master to TEACH mode (free to move by hand)...")
        self.master.MotionCtrl_2(0x00, JOINT_CTRL_MODE, 0, VEL_MODE)
        self.master.DisableArm(ENABLE_MOTORS)
        time.sleep(0.5)

        print("--- Setup complete ---\n")
        return True

    def start_mirroring(self):
        """Main loop: read master joints, send to slave."""
        print("=== MIRRORING ACTIVE ===")
        print("Move the master arm - the slave will follow.")
        print("Press Ctrl+C to stop.\n")

        self.running = True
        loop_count = 0

        while self.running:
            # Read master state
            joints = self.master.GetArmJointMsgs().joint_state
            joint_list = [
                joints.joint_1, joints.joint_2, joints.joint_3,
                joints.joint_4, joints.joint_5, joints.joint_6
            ]
            gripper = self.master.GetArmGripperMsgs().gripper_state.grippers_angle

            # Send to slave
            self.slave.MotionCtrl_2(CAN_CTRL_MODE, JOINT_CTRL_MODE, MOVE_SPEED, VEL_MODE)
            self.slave.JointCtrl(*joint_list)
            self.slave.GripperCtrl(abs(gripper), GRIPPER_EFFORT, GRIPPER_CODE, 0)

            # Print status periodically (every ~1 second)
            loop_count += 1
            if loop_count % 200 == 0:
                joint_deg = [j * 0.001 for j in joint_list]
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
        if not controller.setup():
            print("Failed to set up arms. Exiting.")
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
