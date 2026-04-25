# Dual Piper Control

Replicate movement from one Piper robotic arm to another using the official hardware master/slave mode. The master arm is moved by hand and the slave follows automatically through the CAN bus.

## Prerequisites

- Two Piper robotic arms
- One USB CAN adapter (both arms share one bus)
- Y-splitter CAN cable or CAN hub to connect both arms to the adapter
- Python 3
- System packages:
  ```bash
  sudo apt install ethtool can-utils
  ```

## Installation

```bash
python3 -m venv piper_env
source piper_env/bin/activate
pip install -r requirements.txt
```

## One-Time Configuration

Each arm must be configured with its role (master or slave). This only needs to be done once per arm — the setting is saved on the arm.

### Step 1: Activate CAN

```bash
sudo bash piper_sdk/can_activate.sh can0 1000000
```

### Step 2: Configure each arm

Connect one arm at a time to the CAN adapter and run:

```bash
bash reset.sh
```

This will prompt you to:
1. Connect the master arm and press Enter to configure it
2. Disconnect master, connect the slave arm and press Enter to configure it

You can also configure them individually:

```bash
cla   # with master arm connected
python3 reset_arms.py can0 slave     # with slave arm connected
```

### Step 3: Wire both arms to the same CAN bus

1. Power OFF both arms
2. Connect both arms to the same CAN adapter using a Y-splitter cable
3. Power ON the slave arm first
4. Power ON the master arm second
5. Wait a few seconds
6. Move the master arm — the slave will follow

## How It Works

The Piper arms use hardware-level master/slave replication over CAN:

- The master arm (`0xFA`) sends joint control frames (CAN IDs `0x155`, `0x156`, `0x157`, `0x159`)
- The slave arm (`0xFC`) receives these frames and moves to match
- No software control loop is needed — replication happens at the CAN protocol level
- `GetArmJointCtrl()` reads the master arm's control data
- `GetArmJointMsgs()` reads the slave arm's feedback data

## Monitoring

To view real-time joint positions of both arms on the shared CAN bus:

```bash
bash run_dual_piper.sh
```

Or directly:

```bash
python3 dual_piper.py --can can0
```

## Swapping Master and Slave

1. Power off both arms
2. Connect each arm individually and reconfigure:
   ```bash
   python3 reset_arms.py can0 master    # connect new master arm
   python3 reset_arms.py can0 slave     # connect new slave arm
   ```
3. Reconnect both to the same bus, power slave first then master

## Troubleshooting

**Slave doesn't follow master**
- Both arms must be on the same CAN bus (same adapter)
- Power on slave first, then master
- Check CAN cable connections at both arms and the adapter
- Try power cycling both arms

**CAN "Message NOT sent" errors**
- The arm is not powered on or the CAN cable is disconnected
- Check that the CAN adapter is wired to the arm, not just plugged into USB

**Arm stuck or unresponsive**
```bash
python3 piper_reset.py can0
```

**Switching from master to slave mode**
- The arm needs a power cycle after changing its role

## File Reference

| File | Purpose |
|------|---------|
| `reset.sh` | Interactive setup to configure master/slave roles |
| `reset_arms.py` | Configure a single arm as master or slave |
| `run_dual_piper.sh` | Launch the monitoring script |
| `dual_piper.py` | Monitor master/slave joint positions |
| `piper_reset.py` | Send reset command to a stuck arm |
| `setup_can.sh` | Activate the CAN interface |
| `piper_sdk/` | Piper SDK (standalone copy) |
| `piper_utils.py` | Shared utility functions |
| `examples/` | Single-arm example scripts |
