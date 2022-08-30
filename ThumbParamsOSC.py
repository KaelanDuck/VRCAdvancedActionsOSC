import json
import traceback
import openvr
import sys
import os
import time
import ctypes
import argparse
from pythonosc import udp_client

# Argument Parser
parser = argparse.ArgumentParser(description='ThumbParamsOSC: Takes button data from SteamVR and sends it to an OSC-Client')
parser.add_argument('-d', '--debug', required=False, action='store_true', help='prints values for debugging')
parser.add_argument('-i', '--ip', required=False, type=str, help="set OSC ip. Default=127.0.0.1")
parser.add_argument('-p', '--port', required=False, type=str, help="set OSC port. Default=9000")
args = parser.parse_args()

# Set window name on Windows
if os.name == 'nt':
    ctypes.windll.kernel32.SetConsoleTitleW("ThumbParamsOSC")


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


# load config
config = json.load(open(os.path.join(os.path.join(resource_path('config.json')))))
IP = args.ip if args.ip else config["IP"]
PORT = args.port if args.port else config["Port"]

# Set up UDP OSC client
oscClient = udp_client.SimpleUDPClient(IP, PORT)

# Init OpenVR and Actionsets
application = openvr.init(openvr.VRApplication_Utility)
action_path = os.path.join(resource_path(config["BindingsFolder"]), config["ActionManifestFile"])
openvr.VRInput().setActionManifestPath(action_path)
actionSetHandle = openvr.VRInput().getActionSetHandle(config["ActionSetHandle"])

# Set up OpenVR Action Handles

# sets up a dict with osc name and action handle
getActionHandles = lambda cfg : [
    {
        "OSCName": param["OSCName"],
        "ActionHandle": openvr.VRInput().getActionHandle(param["Action"])
    } for param in cfg if not ("Ignore" in param and param["Ignore"] == True)
]

floatActionHandles = getActionHandles(config["FloatParams"])
boolActionHandles = getActionHandles(config["BoolParams"])

# dict with osc name, type of combo action and a list of action handles to go with it
comboActionHandles = [
    {
        "OSCName": param["OSCName"],
        "Type": param["Type"],
        "ActionHandles": [openvr.VRInput().getActionHandle(act) for act in param["Actions"]]
    } for param in config["ComboParams"] if not ("Ignore" in param and param["Ignore"] == True)
]

# used for debug print
max_name_length = max([len(x["OSCName"]) for x in floatActionHandles + boolActionHandles + comboActionHandles])


####################################################################################################

# helper function
def get_digital(actionHandle : openvr.VRActionHandle_t) -> bool:
    """Shorthand for getDigitalActionData(...)"""
    return bool(openvr.VRInput().getDigitalActionData(actionHandle, openvr.k_ulInvalidInputValueHandle).bState)

# helper function
def get_analog(actionHandle : openvr.VRActionHandle_t) -> float:
    """Shorthand for getAnalogActionData(...)"""
    return float(openvr.VRInput().getAnalogActionData(actionHandle, openvr.k_ulInvalidInputValueHandle).x)


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

    # boolean parameters
    OSCMsgs += [{
        "OSCName": param["OSCName"], 
        "Value": get_digital(param["ActionHandle"])
    } for param in boolActionHandles]

    # float parameters
    OSCMsgs += [{
        "OSCName": param["OSCName"], 
        "Value": get_analog(param["ActionHandle"])
    } for param in floatActionHandles]

    # int / bool parameters (combos)
    for param in comboActionHandles:
        # output dictionary
        out = {"OSCName": param["OSCName"]}

        pType = param["Type"]
        if pType == "index_from_bools":
            # Select the index of a digital action that is true, we use the last true action in the list
            index = 0
            for i in range(len(param["ActionHandles"])):
                if get_digital(param["ActionHandles"][i]):
                    index = i + 1
            out["Value"] = index
        elif pType == "bool_and":
            # returns true if all listed digital actions are true
            out["Value"] = all([get_digital(ah) for ah in param["ActionHandles"]])
        elif pType == "bool_or":
            # returns true if all listed digital actions are true
            out["Value"] = any([get_digital(ah) for ah in param["ActionHandles"]])
        else:
            raise RuntimeError("combo-type: {} not supported".format(pType))
        
        OSCMsgs += [out] # append as an array to append a single element
    
    # send all the messages!
    for msg in OSCMsgs:
        oscClient.send_message(f'/avatar/parameters/{msg["OSCName"]}', msg["Value"])

    # debug output
    if args.debug:
        ints =   [msg for msg in OSCMsgs if type(msg["Value"]) == int]
        floats = [msg for msg in OSCMsgs if type(msg["Value"]) == float]
        bools =  [msg for msg in OSCMsgs if type(msg["Value"]) == bool]

        # dashes in the headers should line up with the data width
        # as the name length is variable and we use the maximum
        dashes = '-' * (int((max_name_length+12)/2) - 4)

        move(10, 0)
        print("DEBUG OUTPUT:")
        if ints:
            print(dashes + "- Ints -" + dashes)
            for m in ints:
                print(f"{m['OSCName']:<{max_name_length}s} : {m['Value']:d}")
        if floats:
            print(dashes + " Floats " + dashes)
            for m in floats:
                print(f"{m['OSCName']:<{max_name_length}s} : {m['Value']:.6f}")
        if bools:
            print(dashes + "- Bools " + dashes)
            for m in bools:
                print(f"{m['OSCName']:<{max_name_length}s} : {str(m['Value'])} ")


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
        cls()
        print("UNEXPECTED ERROR\n")
        print("Please Create an Issue on GitHub with the following information:\n")
        traceback.print_exc()
        input("\nPress ENTER to exit")
        exit()
