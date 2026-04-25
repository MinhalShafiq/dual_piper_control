# Dual Piper Control

Replicate movement from one Piper robotic arm to another in real-time. One arm acts as the **master** (moved by hand) and the other as the **slave** (follows automatically).

## How It Works

1. Both arms connect over separate CAN interfaces (one USB CAN adapter per arm)
2. Both arms reset to their zero/home position (separate step, can be run anytime)
3. The master arm enters teach mode (motors disabled, free to move by hand)
4. The slave arm enters CAN control mode
5. At 200Hz, the master's joint angles and gripper state are read and sent to the slave
6. The slave mirrors the master's position in real-time

## Repository Structure

```
dual_piper_control/
├── run_dual_piper.sh   # Full launcher (reset + mirror)
├── reset.sh            # Standalone reset (use anytime)
├── reset_arms.py       # Reset script (Python)
├── dual_piper.py       # Mirroring script (Python)
├── setup_can.sh        # CAN interface setup
├── piper_utils.py      # Shared utilities
├── piper_sdk/          # Piper SDK
├── examples/           # Single-arm example scripts
└── README.md
```

## Prerequisites

- Two Piper robotic arms, each connected to its own USB CAN adapter
- Python 3 with virtual environment
- System packages:
  ```bash
  sudo apt install ethtool can-utils
  ```

## Installation

### 1. Create virtual environment

```bash
python3 -m venv piper_env
source piper_env/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
sudo apt update && sudo apt install can-utils ethtool
```

## Setup

### 1. Activate CAN Interfaces

Each arm needs its own CAN adapter. Activate them with:

```bash
# If you have two CAN adapters (can0 and can1 auto-detected):
sudo ip link set can0 type can bitrate 1000000 && sudo ip link set can0 up
sudo ip link set can1 type can bitrate 1000000 && sudo ip link set can1 up
```

Or use the provided script (edit `USB_PORTS` inside to match your hardware first):

```bash
sudo bash setup_can.sh
```

To find which USB port maps to which CAN interface:

```bash
sudo ethtool -i can0 | grep bus-info
sudo ethtool -i can1 | grep bus-info
```

Verify both are up:

```bash
ip -br link show type can
```

### 2. Choose Master and Slave

Edit the top of `run_dual_piper.sh`:

```bash
MASTER="can0"    # Arm you move by hand
SLAVE="can1"     # Arm that follows
```

Swap the values to reverse which arm leads. The same config is in `reset.sh`:

```bash
LEFT="can0"
RIGHT="can1"
```

## Usage

### Full run (reset + mirror)

```bash
bash run_dual_piper.sh
```

This resets both arms to zero first, then starts mirroring.

### Reset only (use anytime)

```bash
bash reset.sh              # reset both arms
bash reset.sh left         # reset left arm only
bash reset.sh right        # reset right arm only
```

Or directly with Python:

```bash
python3 reset_arms.py --left can0 --right can1
python3 reset_arms.py --left can0                # left only
python3 reset_arms.py --right can1               # right only
```

### Mirror only (arms already at zero)

```bash
python3 dual_piper.py --master can0 --slave can1
```

### What happens during mirroring

1. Slave arm enables and enters CAN joint control mode
2. Master arm enters teach mode (motors disabled, free to move by hand)
3. Joint positions are printed every ~1 second
4. Press **Ctrl+C** to stop (both arms are disabled safely)

## Troubleshooting

### CAN interfaces not found

Make sure both USB CAN adapters are plugged in. Check what's available:

```bash
ip -br link show type can
```

If an interface is down, bring it up manually:

```bash
sudo ip link set can0 type can bitrate 1000000 && sudo ip link set can0 up
```

### Arm fails to enable

- Check that the arm is powered on and CAN cables are connected
- The script waits up to 10 seconds; if it times out, power cycle the arm
- Try running `piper_sdk/demo/V2/piper_reset.py` for a single arm to clear errors
- Check control mode with `piper_sdk/demo/V2/piper_status.py`

### Arm doesn't move to zero during reset

- Make sure the arm successfully entered CAN control mode (look for `ctrl_mode: 1` in output)
- If stuck, press the button on the robot and try `piper_sdk/demo/V2/piper_reset.py` first

### Slave doesn't follow smoothly

- Make sure both CAN adapters are on separate USB ports (not through the same hub)
- The control loop runs at 200Hz; increase `LOOP_RATE` in `dual_piper.py` if needed
