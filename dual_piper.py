#!/usr/bin/env python3
"""
Dual Piper Control - Replicate movement from master arm to slave arm.

The master arm is set to teach mode (free to move by hand).
The slave arm mirrors the master's joint positions in real-time.

Run reset.sh first to bring both arms to zero position.

Usage:
    python3 dual_piper.py --master can0 --slave can1
"""

import sys
import os
import time
import signal
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from piper_control import piper_interface, piper_init

# Constants
LOOP_RATE = 0.005           # 200Hz control loop
JOINT_ZERO_THRESHOLD = 500  # 0.5 degrees in 0.001 deg units


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
        self.master = piper_interface.PiperInterface(can_port=self.master_can)
        print(f"  Master connected.")

        print(f"Connecting to slave arm on {self.slave_can}...")
        self.slave = piper_interface.PiperInterface(can_port=self.slave_can)
        print(f"  Slave connected.")

        time.sleep(2)

    def _joints_at_zero(self, robot):
        joints = robot.piper.GetArmJointMsgs().joint_state
        return (
            abs(joints.joint_1) < JOINT_ZERO_THRESHOLD and
            abs(joints.joint_2) < JOINT_ZERO_THRESHOLD and
            abs(joints.joint_3) < JOINT_ZERO_THRESHOLD and
            abs(joints.joint_4) < JOINT_ZERO_THRESHOLD and
            abs(joints.joint_5) < JOINT_ZERO_THRESHOLD and
            abs(joints.joint_6) < JOINT_ZERO_THRESHOLD
        )

    def _print_joint_positions(self, robot, name):
        joints = robot.piper.GetArmJointMsgs().joint_state
        gripper = robot.piper.GetArmGripperMsgs().gripper_state.grippers_angle
        print(
            f"  {name} joints (deg): "
            f"J1={joints.joint_1 * 0.001:7.2f}  J2={joints.joint_2 * 0.001:7.2f}  "
            f"J3={joints.joint_3 * 0.001:7.2f}  J4={joints.joint_4 * 0.001:7.2f}  "
            f"J5={joints.joint_5 * 0.001:7.2f}  J6={joints.joint_6 * 0.001:7.2f}  "
            f"Grip={gripper * 0.001:.1f}"
        )

    def setup(self):
        """Verify arms are at zero, enable slave for CAN control, set master to teach mode."""
        print("\n--- Setting up arms ---")

        # Verify both arms are at zero position
        print("  Checking arm positions...")
        self._print_joint_positions(self.master, "Master")
        self._print_joint_positions(self.slave, "Slave")

        if not self._joints_at_zero(self.master):
            print("  ERROR: Master is NOT at zero position!")
            print("  Run 'bash reset.sh' first.")
            return False
        if not self._joints_at_zero(self.slave):
            print("  ERROR: Slave is NOT at zero position!")
            print("  Run 'bash reset.sh' first.")
            return False
        print("  Both arms confirmed at zero.")

        # Enable slave arm with CAN joint control
        print("  Enabling slave arm...")
        piper_init.reset_arm(
            self.slave,
            arm_controller=piper_interface.ArmController.POSITION_VELOCITY,
            move_mode=piper_interface.MoveMode.JOINT,
        )
        piper_init.reset_gripper(self.slave)
        print("  Slave in CAN joint control mode.")

        # Set master to teach mode (disable motors so it can be moved by hand)
        print("  Setting master to TEACH mode (free to move by hand)...")
        self.master.disable_arm()
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
            joints = self.master.piper.GetArmJointMsgs().joint_state
            joint_list = [
                joints.joint_1, joints.joint_2, joints.joint_3,
                joints.joint_4, joints.joint_5, joints.joint_6
            ]
            gripper = self.master.piper.GetArmGripperMsgs().gripper_state.grippers_angle

            # Send to slave
            self.slave.piper.MotionCtrl_2(0x01, 0x01, 100, 0x00)
            self.slave.piper.JointCtrl(*joint_list)
            self.slave.piper.GripperCtrl(abs(gripper), 1000, 0x01, 0)

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
        if not self.running and not self.master and not self.slave:
            return
        self.running = False
        print("\n\n=== STOPPING ===")

        if self.slave:
            print("Disabling slave arm...")
            try:
                self.slave.disable_arm()
            except Exception as e:
                print(f"  Warning: {e}")

        if self.master:
            print("Disabling master arm...")
            try:
                self.master.disable_arm()
            except Exception as e:
                print(f"  Warning: {e}")

        print("Arms disabled.")

    def disconnect(self):
        if self.master:
            try:
                self.master.piper.DisconnectPort()
            except Exception:
                pass
            self.master = None
        if self.slave:
            try:
                self.slave.piper.DisconnectPort()
            except Exception:
                pass
            self.slave = None


def main():
    parser = argparse.ArgumentParser(
        description="Dual Piper Control - Mirror master arm movements to slave arm"
    )
    parser.add_argument(
        "--master", required=True,
        help="CAN interface for the master arm (e.g. can0)"
    )
    parser.add_argument(
        "--slave", required=True,
        help="CAN interface for the slave arm (e.g. can1)"
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
