from array import array
from dataclasses import dataclass
import json
from types import CodeType
from typing import Any, Iterable
import yaml
import traceback
import openvr
import openvr.error_code
import sys
import os
import time
import ctypes
import argparse
import re
from pythonosc import udp_client

# use these for eval expressions
import numpy as np
import math
import glm

# Argument Parser
parser = argparse.ArgumentParser(description='ThumbParamsOSC: Takes button data from SteamVR and sends it to an OSC-Client')
parser.add_argument('-d', '--debug', required=False, action='store_true', help='prints values for debugging')
parser.add_argument('-i', '--ip', required=False, type=str, help="set OSC ip. Default=127.0.0.1")
parser.add_argument('-p', '--port', required=False, type=str, help="set OSC port. Default=9000")
args = parser.parse_args()

# keep eval somewhat safe
eval_allowed_builtins = {x: eval(x) for x in ['abs', 'all', 'any', 'bool', 'complex', 'divmod', 'float', 'int', 'len', 'max', 'min', 'pow', 'round', 'sum']}
eval_globals = {"__builtins__": eval_allowed_builtins, "np": np, "math": math, "glm": glm}

# Set window name on Windows
if os.name == 'nt':
    ctypes.windll.kernel32.SetConsoleTitleW("ThumbParamsOSC")

##################################################
# some classes for storing data
@dataclass
class ActionHandle:
    handle : str
    action_name : str
    subattrs : Iterable[str]
    type: str

@dataclass
class BasicParameter:
    name : str
    actionHandle : ActionHandle

@dataclass
class CustomParameter:
    name : str
    expression : CodeType
    actionHandles : Iterable[ActionHandle]

@dataclass
class OSCMessage:
    path : str
    value : Any

# this class is passed to the eval function for pose types
@dataclass
class DevicePose:
    matrix : glm.mat4
    position : glm.vec3
    rotation : glm.quat
    velocity : glm.vec3
    angvelocity : glm.vec3

# skeleton data classes
# use named attributes for easy referencing in an action
class FingerDataCurl(list):
    def __new__(cls, arr) -> 'FingerDataCurl':
        self = super().__new__(cls, arr)
        self.thumb  : float = arr[0]
        self.index  : float = arr[1]
        self.middle : float = arr[2]
        self.ring   : float = arr[3]
        self.pinky  : float = arr[4]
        return self

class FingerDataSplay(list):
    def __new__(cls, arr) -> 'FingerDataSplay':
        self = super().__new__(cls, arr)
        self.index  : float = arr[0]
        self.middle : float = arr[1]
        self.ring   : float = arr[2]
        self.pinky  : float = arr[3]
        return self

@dataclass
class HandSkeleton:
    fingerCurl : FingerDataCurl
    fingerSplay : FingerDataSplay

###############################################

def move(y, x):
    """Moves console cursor."""
    print("\033[%d;%dH" % (y, x))


def cls():
    """Clears Console"""
    os.system('cls' if os.name == 'nt' else 'clear')


def resource_path(relative_path):
    """Gets absolute path from relative path"""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

###########################################################################################################

# load config
config = yaml.safe_load(open(resource_path('config.yaml')))
IP = args.ip if args.ip else config["IP"]
PORT = args.port if args.port else config["Port"]

# Set up UDP OSC client
oscClient = udp_client.SimpleUDPClient(IP, PORT)

# Init OpenVR and Actionsets
application = openvr.init(openvr.VRApplication_Utility)
action_path = os.path.join(resource_path(config["BindingsFolder"]), config["ActionManifestFile"])
openvr.VRInput().setActionManifestPath(action_path)
actionSetHandle = openvr.VRInput().getActionSetHandle(config["ActionSetHandle"])
actionSetHandleString = config["ActionSetHandle"] + "/in/"

def action_base_name(act : str):
    return act.split(".")[0]

def action_attr_names(act : str):
    parts = act.split(".")
    if len(parts) == 1:
        return []
    else:
        return parts[1:]

# use the action set to map action names to their types, we will use this later
typemap = {tp["name"].split("/")[-1]: tp["type"] for tp in json.load(open(action_path))["actions"]}

final_value_type_check_has_run = False

# check the actions specified in the config are actually in the action set, otherwise openvr will bork
for name,act in config["Params"].items():
    action = action_base_name(act)
    if action not in typemap:
        raise RuntimeError(f"Action in config not in action map: {action}")
for param in config["CustomParams"]:
    for act in param["Actions"]:
        action = action_base_name(act)
        if action not in typemap:
            raise RuntimeError(f"Action in config not in action map: {action}")

# Set up OpenVR Action Handles

# config->Params
# turn the parameter name into an actionhandle and store the type beside it
basicParameters = [
    BasicParameter(
        name = name,
        actionHandle = ActionHandle(
            handle = openvr.VRInput().getActionHandle(actionSetHandleString + action_base_name(act)),
            action_name = act,
            subattrs = action_attr_names(act),
            type = typemap[action_base_name(act)]
        )
    ) for name,act in config["Params"].items()
]

# quick and probably insecure check for double underscores in custom action handles
#NOTE: this is not secure, but probably secure enough to stop undetermined people trying to pry it open
for param in config["CustomParams"]:
    if "__" in param["Expression"]:
        raise RuntimeError(f"Possibly unsafe expression in parameter {param['OSCName']}: {param['Expression']}")

# config->CustomParams
# store a list of actionhandles for each parameter as per the config
customParameters = [
    CustomParameter(
        name = param["OSCName"],
        expression = compile(param["Expression"], 'config.yaml', 'eval'), # compile the expression to use with eval later
        actionHandles = [ActionHandle(
            handle = openvr.VRInput().getActionHandle(actionSetHandleString + action_base_name(act)),
            action_name = act,
            subattrs = action_attr_names(act),
            type = typemap[action_base_name(act)]
        ) for act in param["Actions"]]
    ) for param in config["CustomParams"]
]

# used for debug print
# use [0] for testing purposes when we don't export any parameters
max_name_length = max([0] + [len(x.name) for x in basicParameters + customParameters])

####################################################################################################

# helper function
def get_digital(actionHandle : openvr.VRActionHandle_t) -> bool:
    """Shorthand for getDigitalActionData(...)"""
    return bool(openvr.VRInput().getDigitalActionData(actionHandle, openvr.k_ulInvalidInputValueHandle).bState)

# helper function
def get_analog(actionHandle : openvr.VRActionHandle_t) -> float:
    """Shorthand for getAnalogActionData(...).x"""
    return float(openvr.VRInput().getAnalogActionData(actionHandle, openvr.k_ulInvalidInputValueHandle).x)

# returns a DevicePose object used by an eval function
def get_pose(actionHandle : openvr.VRActionHandle_t) -> DevicePose:
    pose : openvr.TrackedDevicePose_t = openvr.VRInput().getPoseActionDataForNextFrame(actionHandle, openvr.TrackingUniverseStanding, openvr.k_ulInvalidInputValueHandle).pose
    m = pose.mDeviceToAbsoluteTracking.m
    # type converting through numpy seems to make it happy
    matrix : glm.mat4 = glm.mat4(glm.mat4x3(np.mat([m[0], m[1], m[2]])))
    pos = glm.vec3()
    rot = glm.quat()
    glm.decompose(matrix, glm.vec3(), rot, pos, glm.vec3(), glm.vec4())
    return DevicePose(
        matrix = matrix,
        position = pos,
        rotation = rot,
        velocity = glm.vec3(pose.vVelocity.v[0], pose.vVelocity.v[1], pose.vVelocity.v[2]),
        angvelocity = glm.vec3(pose.vAngularVelocity.v[0], pose.vAngularVelocity.v[1], pose.vAngularVelocity.v[2])
    )

# returns a glm.vec2 for any vector2 types (joystick, trackpad)
def get_vec2(actionHandle : openvr.VRActionHandle_t) -> glm.vec2:
    iaad = openvr.VRInput().getAnalogActionData(actionHandle, openvr.k_ulInvalidInputValueHandle)
    return glm.vec2(iaad.x, iaad.y)

def get_skeleton(actionHandle : openvr.VRActionHandle_t) -> HandSkeleton:
    try:
        skelly : openvr.VRSkeletalSummaryData_t = openvr.VRInput().getSkeletalSummaryData(actionHandle, openvr.VRSummaryType_FromDevice)
        curl = [float(x) for x in skelly.flFingerCurl]
        splay = [float(x) for x in skelly.flFingerSplay]
    except openvr.error_code.InputError_NoData:
        curl = [0.0] * 5
        splay = [0.0] * 4

    return HandSkeleton(FingerDataCurl(curl), FingerDataSplay(splay))

###########################################

# use the correct function to resolve the action handle to a value
def get_value(actionHandle : ActionHandle):
    if actionHandle.type == "boolean":
        val = get_digital(actionHandle.handle)
    elif actionHandle.type == "vector1":
        val = get_analog(actionHandle.handle)
    elif actionHandle.type == "pose":
        val = get_pose(actionHandle.handle)
    elif actionHandle.type == "vector2":
        val = get_vec2(actionHandle.handle)
    elif actionHandle.type == "skeleton":
        val = get_skeleton(actionHandle.handle)
    
    # iterate through attributes to get what's specified in the config
    for attr in actionHandle.subattrs:
        val = getattr(val, attr, None)
    
    # getattr will set to None instead of raising exception when there is a missing attribute
    if val == None:
        raise RuntimeError(f"Unable to resolve attributes for action: {actionHandle.action_name}")
    
    return val


##################################################

def handle_input():
    """Handles all the OpenVR Input and sends it via OSC"""
    # Set up OpenVR events and Action sets
    event = openvr.VREvent_t()
    has_events = True
    while has_events:
        has_events = application.pollNextEvent(event)
    _actionsets = (openvr.VRActiveActionSet_t * 1)()
    _actionset = _actionsets[0]
    _actionset.ulActionSet = actionSetHandle
    openvr.VRInput().updateActionState(_actionsets)

    # list of messages to be sent to OSC later
    OSCMsgs = []

    if "ConnectedParam" in config:
        OSCMsgs += [OSCMessage(config["ConnectedParam"],True)]

    # basic parameters
    OSCMsgs += [OSCMessage(
        path = param.name, 
        value = get_value(param.actionHandle) 
    ) for param in basicParameters]

    # custom expression parameters
    OSCMsgs += [OSCMessage(
        path = param.name,
        value = eval(
            param.expression,
            eval_globals,
            {"v": [get_value(ah) for ah in param.actionHandles]}
        )
    ) for param in customParameters]

    # check all the types are valid
    global final_value_type_check_has_run
    if not final_value_type_check_has_run:
        final_value_type_check_has_run = True    # performance
        for msg in OSCMsgs:
            if type(msg.value) not in [float, int, bool]:
                raise RuntimeError(f"Parameter {msg.path} has invalid type, must be bool/float/int, found: {type(msg.value)}")

    # send all the messages!
    for msg in OSCMsgs:
        oscClient.send_message(f'/avatar/parameters/{msg.path}', msg.value)

    # debug output
    if args.debug:
        ints =   [msg for msg in OSCMsgs if type(msg.value) == int]
        floats = [msg for msg in OSCMsgs if type(msg.value) == float]
        bools =  [msg for msg in OSCMsgs if type(msg.value) == bool]

        # dashes in the headers should line up with the data width
        # as the name length is variable and we use the maximum
        dashes = '-' * (int((max_name_length+12)/2) - 4)

        move(10, 0)
        print("DEBUG OUTPUT:")
        if ints:
            print(dashes + "- Ints -" + dashes)
            for m in ints:
                print(f"{m.path:<{max_name_length}s} : {m.value:d}")
        if floats:
            print(dashes + " Floats " + dashes)
            for m in floats:
                print(f"{m.path:<{max_name_length}s} : {m.value:.6f}")
        if bools:
            print(dashes + "- Bools " + dashes)
            for m in bools:
                print(f"{m.path:<{max_name_length}s} : {str(m.value)} ")


cls()
print("ThumbParamsOSC running...\n")
print("IP:\t\t", IP)
print("Port:\t\t", PORT)
print("\nYou can minimize this window.")
print("\nPress CTRL + C to exit or just close the window.")

# Main Loop
while True:
    try:
        handle_input()
        time.sleep(0.005)
    except KeyboardInterrupt:
        cls()
        exit()
    except Exception:
        #cls()
        print("UNEXPECTED ERROR\n")
        print("Please Create an Issue on GitHub with the following information:\n")
        traceback.print_exc()
        #input("\nPress ENTER to exit")
        exit()
