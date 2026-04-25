import piper_sdk
import time
import numpy as np


# Magic values
CAN_CTRL_MODE = 0x01
POS_VELOCITY_MODE = 0x00
MOVE_POSITION_MODE = 0x00
USE_ALL_MOTOR = 0x07


def enable_fun(piper:piper_sdk.C_PiperInterface_V2):
    '''
    Enable the robot and check the enable status for 5 seconds. If the enable timeout occurs, exit the program.
    '''
    print("Enabling the robot")
    enable_flag = False
    timeout = 5
    start_time = time.time()
    elapsed_time_flag = False
    while not (enable_flag):
        elapsed_time = time.time() - start_time
        print("--------------------")
        enable_flag = piper.GetArmLowSpdInfoMsgs().motor_1.foc_status.driver_enable_status and \
            piper.GetArmLowSpdInfoMsgs().motor_2.foc_status.driver_enable_status and \
            piper.GetArmLowSpdInfoMsgs().motor_3.foc_status.driver_enable_status and \
            piper.GetArmLowSpdInfoMsgs().motor_4.foc_status.driver_enable_status and \
            piper.GetArmLowSpdInfoMsgs().motor_5.foc_status.driver_enable_status and \
            piper.GetArmLowSpdInfoMsgs().motor_6.foc_status.driver_enable_status
        print("Enabled: ", enable_flag)

        print("--------------------")
        # Check if the timeout has been exceeded
        if elapsed_time > timeout:
            print("!!! Timeout !!!")
            elapsed_time_flag = True
            enable_flag = True
            break
        time.sleep(1)
        pass
    if(elapsed_time_flag):
        print("The program has automatically timed out, exiting the program")
        exit(0)


def get_end_pose(piper:piper_sdk.C_PiperInterface_V2):
    """
    Retrieves the end effector pose from the Piper interface.

    This function queries the Piper interface to get the current end effector pose,
    which includes the position, rotation of the end effector and gripper angle. The position is
    returned as a 3-element array representing the X, Y, and Z coordinates in 0.001 mm.
    The rotation is returned as a 3-element array representing the rotation around the
    X, Y, and Z axes in 0.001 degrees. Gripper angle is returned in 0.001°.

    Parameters:
        piper (piper_sdk.C_PiperInterface_V2): An instance of the Piper interface.

    Returns:
        tuple: A tuple containing two numpy arrays:
            - position (numpy.ndarray): A 3-element array representing the position
              (X, Y, Z) in 0.001 mm.
            - rotation (numpy.ndarray): A 3-element array representing the rotation
              (RX, RY, RZ) in 0.001 degrees.
            - gripper_angle (int): The gripper angle in 0.001°.
    """
    end_pose = piper.GetArmEndPoseMsgs().end_pose
    position = np.array([end_pose.X_axis, end_pose.Y_axis, end_pose.Z_axis])
    rotation = np.array([end_pose.RX_axis, end_pose.RY_axis, end_pose.RZ_axis])
    gripper_angle = piper.GetArmGripperMsgs().gripper_state.grippers_angle
    return position, rotation, gripper_angle


def wait_end_of_movement(piper: piper_sdk.C_PiperInterface_V2, sleep_time: float = 0.1):
    """
    Waits until the robot's arm and gripper stops moving.

    This function continuously checks the motion status of the robot's arm and waits
    until the motion status indicates that the arm is no longer moving.

    Parameters:
        piper (piper_sdk.C_PiperInterface_V2): An instance of the Piper interface.
        sleep_time (float): The time to wait (in seconds) between status checks. Default is 0.1 seconds.

    Returns:
        None
    """
    gripper_angle = piper.GetArmGripperMsgs().gripper_state.grippers_angle
    move_status = 1  # Initial motion status indicating movement
    time.sleep(sleep_time)
    # Check if arm is moving
    while move_status:
        move_status = piper.GetArmStatus().arm_status.motion_status
        time.sleep(sleep_time)
    # Check if gripper is moving
    while gripper_angle != piper.GetArmGripperMsgs().gripper_state.grippers_angle:
        gripper_angle = piper.GetArmGripperMsgs().gripper_state.grippers_angle
        time.sleep(sleep_time)
