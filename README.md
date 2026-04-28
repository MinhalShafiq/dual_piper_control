# Dual Piper Control

Run two AgileX Piper arms in master/slave mode: move the master arm by hand, and the slave arm mirrors it in real time. Joint replication is handled at the CAN protocol level by the arms themselves; this repo configures the arms, brings up the bus, monitors both arms, and bridges the gripper (the only piece that doesn't auto-follow).

## Hardware setup

- 2 × AgileX Piper arm
- 1 × USB CAN adapter (both arms share one bus — do **not** use two adapters)
- 1 × Y-splitter CAN cable or CAN hub so both arms connect to the same adapter
- A single shared 24 V power supply or two supplies that are switched on together

## How it works

Piper arms support a hardware-level master/slave linkage over CAN:

- Master arm (`0xFA`) broadcasts its joint state on CAN IDs `0x155`, `0x156`, `0x157`, `0x159`.
- Slave arm (`0xFC`) listens on the same bus and moves to match. No software loop is needed for joints.
- The **gripper** module is independently enabled and does **not** auto-follow. `dual_piper.py` reads master's gripper command (`GetArmGripperCtrl`) and forwards it to the slave (`GripperCtrl`) every loop.
- The role (master/slave) is written to each arm's flash via `MasterSlaveConfig` and persists across power cycles.

Useful SDK calls:

| Call | What it returns |
|------|-----------------|
| `GetArmJointCtrl()` | Master arm's joint command (what master is sending) |
| `GetArmGripperCtrl()` | Master arm's gripper command |
| `GetArmJointMsgs()` | Slave arm's actual joint feedback |
| `GetArmGripperMsgs()` | Slave arm's actual gripper feedback |

## Install

System packages:

```bash
sudo apt install ethtool can-utils
```

Python environment:

```bash
python3 -m venv piper_env
source piper_env/bin/activate
pip install -r requirements.txt
```

## First-time setup

Each arm must be told its role and have its gripper parameters written. This is a one-time step per arm — both settings are saved to the arm's flash.

### 1. Bring up the CAN interface

```bash
sudo bash setup_can.sh
```

This creates `can0` at 1 Mbit/s. If you have multiple USB CAN adapters, set `USB_ADDRESS` inside `setup_can.sh` (find it via `sudo ethtool -i can0 | grep bus-info`).

### 2. Configure each arm individually

Connect **one arm at a time** to the CAN adapter, then run:

```bash
bash reset.sh
```

This walks you through:

1. Plug in the master arm → press Enter → it gets configured as `0xFA` and gripper params are written.
2. Unplug master, plug in the slave arm → press Enter → it gets configured as `0xFC` and gripper params are written.

Or do them individually:

```bash
python3 reset_arms.py can0 master    # connect master arm
python3 reset_arms.py can0 slave     # connect slave arm
```

`reset_arms.py` only writes config to the arm's flash — it sends no motion commands, so the arm stays still.

### 3. Wire both arms to the shared bus

1. Power **OFF** both arms.
2. Connect both arms to the same CAN adapter via the Y-splitter.
3. Power **ON** both arms (simultaneous power-on is fine).
4. Run the control script (see below).

Note: the slave will jump to whatever pose the master is in when the script starts. To avoid a jump on startup, position the master roughly where the slave is before you launch.

## Run

```bash
bash run_dual_piper.sh
```

or directly:

```bash
python3 dual_piper.py --can can0
```

You should see the slave enable, high-follow mode activate, and joint/gripper readings print every ~2 s. Move the master by hand and the slave follows. Press Ctrl+C to stop.

## Swapping master and slave

Roles are stored on the arm itself. To swap:

1. Power off both arms and disconnect them from the bus.
2. Connect each one individually and rerun:
   ```bash
   python3 reset_arms.py can0 master    # the new master
   python3 reset_arms.py can0 slave     # the new slave
   ```
3. Reconnect both to the shared bus and power on.

## Troubleshooting

**Slave doesn't follow master**
- Both arms must be on the same CAN bus (one adapter, Y-splitter).
- Confirm role assignment: rerun `reset.sh`.
- Verify CAN traffic with `candump can0` — you should see frames `0x155`–`0x159` (master) and `0x2A5`–`0x2A7` (slave feedback).

**Slave gripper doesn't move or shows no data**
- The gripper module needs its parameters written once. `reset_arms.py` does this via `GripperTeachingPendantParamConfig(100, 70)`. Rerun `reset.sh` if you skipped it.
- The gripper does **not** auto-follow at the firmware level — `dual_piper.py` must be running for the gripper to mirror.

**Slave gripper is slow**
- `dual_piper.py` forwards master's `grippers_effort` directly to the slave, falling back to 3000 (3 N·m) if master reports 0. If it still feels weak, raise the fallback in `dual_piper.py`.

**`Message NOT sent` / no CAN response**
- The arm isn't powered, or the CAN cable isn't seated. Check both ends of the cable.
- The CAN interface may not be up — rerun `sudo bash setup_can.sh`.

**Arm stuck or unresponsive (after an emergency stop, etc.)**
```bash
python3 piper_reset.py can0
```
This sends `MotionCtrl_1(0x02, 0, 0)` (resume) and `MotionCtrl_2(0, 0, 0, 0x00)` (position/velocity mode).

**Slave drifts off after a while**
- `dual_piper.py` re-sends `EnableArm(7)` and high-follow mode every ~0.5 s for exactly this reason. If it still drifts, check for CAN bus errors (`ip -s -d link show can0`).

## File reference

| File | Purpose |
|------|---------|
| `setup_can.sh` | Brings up the CAN interface at 1 Mbit/s |
| `reset.sh` | Interactive wrapper to configure both arms one at a time |
| `reset_arms.py` | Configures one arm: writes master/slave role + gripper params |
| `dual_piper.py` | Main control script: enables slave, relays gripper, monitors both arms |
| `run_dual_piper.sh` | Thin launcher for `dual_piper.py` |
| `piper_reset.py` | Emergency reset for a stuck arm |
| `piper_utils.py` | Shared helper functions used by examples |
| `piper_sdk/` | Vendored AgileX Piper SDK (so this repo is self-contained) |
| `examples/` | Single-arm reference scripts from the SDK |
| `requirements.txt` | Python dependencies |
