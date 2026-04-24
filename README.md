# Dual Piper Control

Replicate movement from one Piper robotic arm to another in real-time. One arm acts as the **master** (moved by hand) and the other as the **slave** (follows automatically).

## How It Works

1. Both arms connect over separate CAN interfaces (one USB CAN adapter per arm)
2. Both arms reset to their zero/home position
3. The master arm enters teach mode (motors disabled, free to move by hand)
4. The slave arm enters CAN control mode
5. At 200Hz, the master's joint angles and gripper state are read and sent to the slave
6. The slave mirrors the master's position in real-time

## Repository Structure

```
dual_piper_control/
├── run_dual_piper.sh   # Main launcher script (edit master/slave here)
├── setup_can.sh        # CAN interface setup for two adapters
├── dual_piper.py       # Python control script
├── piper_sdk/          # Piper SDK (standalone copy)
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
  pip install python-can
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

This names and activates both CAN interfaces at 1Mbps.

### 3. Choose Master and Slave

Edit the top of `run_dual_piper.sh`:

```bash
MASTER="can_left"    # Arm you move by hand
SLAVE="can_right"    # Arm that follows
```

Swap the values to reverse which arm leads.

## Usage

```bash
bash run_dual_piper.sh
```

What happens:
1. Both arms enable and move to the zero/home position
2. Arms are held at zero for a few seconds to stabilize
3. Master arm releases (teach mode) -- you can now move it by hand
4. Slave arm follows the master's movements in real-time
5. Joint positions are printed every ~1 second
6. Press **Ctrl+C** to stop (both arms are disabled safely)

You can also run the Python script directly:

```bash
python3 dual_piper.py --master can_left --slave can_right
```

## Troubleshooting

### CAN interfaces not found

Make sure both USB CAN adapters are plugged in, then re-run `sudo bash setup_can.sh`. Check available interfaces with:

```bash
ip -br link show type can
```

### Arm fails to enable

- Check that the arm is powered on
- Check CAN cable connections
- The script waits up to 10 seconds for enable; if it times out, power cycle the arm and try again

### Arm drifts after reset

The reset procedure sends repeated zero-position commands and verifies all joints are within 0.5 degrees of zero before proceeding. If drift still occurs, check for mechanical issues or loose joints.

### Slave doesn't follow smoothly

- Make sure both CAN adapters are on separate USB ports (not through the same hub)
- The control loop runs at 200Hz; if your system is slow, increase the `LOOP_RATE` value in `dual_piper.py`
