#!/usr/bin/env python3
"""
Reset a Piper arm (recover from emergency stop / bad state).

This sends MotionCtrl_1 (resume) and MotionCtrl_2 (position/velocity mode)
to clear errors. Use this when an arm is stuck and won't respond to enable.

Usage:
    python3 piper_reset.py can0
    python3 piper_reset.py can1
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from piper_sdk import C_PiperInterface_V2

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 piper_reset.py <can_port>")
        print("  e.g. python3 piper_reset.py can0")
        sys.exit(1)

    can_port = sys.argv[1]
    print(f"Resetting arm on {can_port}...")

    piper = C_PiperInterface_V2(can_port)
    piper.ConnectPort()
    time.sleep(1)

    # Resume from emergency stop
    piper.MotionCtrl_1(0x02, 0, 0)
    time.sleep(0.5)

    # Set to position/velocity mode
    piper.MotionCtrl_2(0, 0, 0, 0x00)
    time.sleep(0.5)

    print(f"Reset command sent to {can_port}.")
    piper.DisconnectPort()
