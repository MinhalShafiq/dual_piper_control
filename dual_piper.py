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
from piper_sdk import C_PiperInterface_V2

# Constants
LOOP_RATE = 0.005           # 200Hz control loop
JOINT_ZERO_THRESHOLD = 500  # 0.5 degrees in 0.001 deg units
ENABLE_TIMEOUT = 10.0


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


def disable_arm(piper, timeout=ENABLE_TIMEOUT):
    start = time.time()
    while time.time() - start < timeout:
        piper.MotionCtrl_1(0x02, 0, 0)
        time.sleep(0.1)
        status = piper.GetArmStatus().arm_status
        if status.ctrl_mode == 0 and status.arm_status == 0:
            return True
        time.sleep(0.5)
    return False


def enable_arm_can_mode(piper, timeout=ENABLE_TIMEOUT):
    start = time.time()
    while time.time() - start < timeout:
        for motor in range(1, 7):
            piper.EnableArm(motor)
        time.sleep(0.1)
        if is_arm_enabled(piper):
            piper.MotionCtrl_2(0x01, 0x01, 100, 0x00)
            time.sleep(0.5)
            return True
        time.sleep(0.5)
    return False


def full_enable(piper, name, max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        print(f"  {name}: enable attempt {attempt}/{max_attempts}...")
        if not disable_arm(piper):
            continue
        if not enable_arm_can_mode(piper):
            continue
        if piper.GetArmStatus().arm_status.ctrl_mode == 1:
            print(f"  {name}: enabled.")
            return True
    print(f"  ERROR: {name} failed to enable!")
    return False


class DualPiperController:
    def __init__(self, master_can, slave_can):
        self.master_can = master_can
        self.slave_can = slave_can
        self.master = None
        self.slave = None
        self.running = False

    def connect(self):
        print(f"Connecting to master arm on {self.master_can}...")
        self.master = C_PiperInterface_V2(self.master_can)
        self.master.ConnectPort()
        print(f"  Master connected.")

        print(f"Connecting to slave arm on {self.slave_can}...")
        self.slave = C_PiperInterface_V2(self.slave_can)
        self.slave.ConnectPort()
        print(f"  Slave connected.")

        print("  Waiting for CAN feedback...")
        time.sleep(2)

    def _joints_at_zero(self, piper):
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
        joints = piper.GetArmJointMsgs().joint_state
        gripper = piper.GetArmGripperMsgs().gripper_state.grippers_angle
        print(
            f"  {name} joints (deg): "
            f"J1={joints.joint_1 * 0.001:7.2f}  J2={joints.joint_2 * 0.001:7.2f}  "
            f"J3={joints.joint_3 * 0.001:7.2f}  J4={joints.joint_4 * 0.001:7.2f}  "
            f"J5={joints.joint_5 * 0.001:7.2f}  J6={joints.joint_6 * 0.001:7.2f}  "
            f"Grip={gripper * 0.001:.1f}"
        )

    def setup(self):
        print("\n--- Setting up arms ---")

        # Verify both arms are at zero position
        print("  Checking arm positions...")
        self._print_joint_positions(self.master, "Master")
        self._print_joint_positions(self.slave, "Slave")

        if not self._joints_at_zero(self.master):
            print("  ERROR: Master is NOT at zero! Run 'bash reset.sh' first.")
            return False
        if not self._joints_at_zero(self.slave):
            print("  ERROR: Slave is NOT at zero! Run 'bash reset.sh' first.")
            return False
        print("  Both arms confirmed at zero.")

        # Enable slave arm with CAN joint control
        print("  Enabling slave arm...")
        if not full_enable(self.slave, "Slave"):
            return False
        self.slave.GripperCtrl(0, 1000, 0x01, 0)

        # Set master to teach mode (disable motors)
        print("  Setting master to TEACH mode (free to move by hand)...")
        self.master.DisableArm(7)
        time.sleep(0.5)

        print("--- Setup complete ---\n")
        return True

    def start_mirroring(self):
        print("=== MIRRORING ACTIVE ===")
        print("Move the master arm - the slave will follow.")
        print("Press Ctrl+C to stop.\n")

        self.running = True
        loop_count = 0

        while self.running:
            joints = self.master.GetArmJointMsgs().joint_state
            joint_list = [
                joints.joint_1, joints.joint_2, joints.joint_3,
                joints.joint_4, joints.joint_5, joints.joint_6
            ]
            gripper = self.master.GetArmGripperMsgs().gripper_state.grippers_angle

            self.slave.MotionCtrl_2(0x01, 0x01, 100, 0x00)
            self.slave.JointCtrl(*joint_list)
            self.slave.GripperCtrl(abs(gripper), 1000, 0x01, 0)

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
            try:
                self.slave.DisableArm(7)
            except Exception:
                pass
        if self.master:
            try:
                self.master.DisableArm(7)
            except Exception:
                pass
        print("Arms disabled.")

    def disconnect(self):
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
    parser.add_argument("--master", required=True, help="CAN interface for master arm")
    parser.add_argument("--slave", required=True, help="CAN interface for slave arm")
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
