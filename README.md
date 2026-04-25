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
- Python 3
- System packages:
  ```bash
  sudo apt install ethtool can-utils
  ```
- Python packages:
  ```bash
  pip install -r requirements.txt
  ```

## Setup

### 1. Find Your CAN USB Addresses

Plug in one CAN adapter at a time and run:

```bash
sudo ethtool -i can0 | grep bus-info
```

Note the `bus-info` value (e.g. `1-2:1.0`) for each adapter.

### 2. Configure CAN Interfaces

Edit the `USB_PORTS` section in `setup_can.sh` with your bus-info values:

```bash
USB_PORTS["1-2:1.0"]="can_left:1000000"
USB_PORTS["1-4:1.0"]="can_right:1000000"
```

Then run:

```bash
sudo bash setup_can.sh
```

### 3. Choose Master and Slave

Edit the top of `run_dual_piper.sh`:

```bash
MASTER="can_left"    # Arm you move by hand
SLAVE="can_right"    # Arm that follows
```

Swap the values to reverse which arm leads.

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
python3 reset_arms.py --left can_left --right can_right
python3 reset_arms.py --left can_left                     # left only
python3 reset_arms.py --right can_right                   # right only
```

### Mirror only (arms already at zero)

```bash
python3 dual_piper.py --master can_left --slave can_right
```

### What happens during mirroring

1. Slave arm enables and enters CAN joint control mode
2. Master arm enters teach mode (motors disabled, free to move by hand)
3. Joint positions are printed every ~1 second
4. Press **Ctrl+C** to stop (both arms are disabled safely)

## Troubleshooting

### CAN interfaces not found

Make sure both USB CAN adapters are plugged in, then run `sudo bash setup_can.sh`. Check available interfaces:

```bash
ip -br link show type can
```

### Arm fails to enable

- Check that the arm is powered on and CAN cables are connected
- The script waits up to 10 seconds; if it times out, power cycle the arm
- Try running `piper_sdk/demo/V2/piper_reset.py` for a single arm to clear errors
- Check control mode with `piper_sdk/demo/V2/piper_status.py`

### Arm drifts after reset

The reset holds the zero position for 3 seconds after reaching it to let the arm stabilize. If drift still occurs, check for mechanical issues.

### Slave doesn't follow smoothly

- Make sure both CAN adapters are on separate USB ports (not through the same hub)
- The control loop runs at 200Hz; increase `LOOP_RATE` in `dual_piper.py` if needed
