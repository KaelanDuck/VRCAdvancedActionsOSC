# <img src="https://raw.githubusercontent.com/I5UCC/VRCThumbParamsOSC/main/icon.ico" width="32" height="32"> AdvancedActionsOSC
OSC program that makes all SteamVR controller actions accessible as Avatar Parameters with a flexible configuration system.

Based on ThumbParamsOSC by [I5UCC](https://github.com/I5UCC)

Works for both VRChat and ChilloutVR but requires an OSC Mod when used in ChilloutVR.

Supports every controller that exposes actions to SteamVR. Including ***Valve-Index*** and ***Oculus(Meta)-Touch*** Controllers. You may need to set the bindings manually for other controllers.

# How to use

Activate OSC in VRChat: <br/><br/>
![EnableOSC](https://user-images.githubusercontent.com/43730681/172059335-db3fd6f9-86ae-4f6a-9542-2a74f47ff826.gif)

In Action menu, got to Options>OSC>Enable <br/>

Then just run the `AdvancedActionsOSC.exe` and you are all set! <br/>
## You might need to restart AdvancedActionsOSC.exe or even SteamVR after first run

## Download from the [releases page](https://github.com/KaelanDuck/VRCAdvancedActionsOSC/releases)

# Configuration

Configuration is done via `config.yaml`, it is intended to be largely human readable.

## Basic settings
| Key | Value |
| --- | --- |
| `IP` | IP address of OSC client |
| `Port` | OSC client listen port |
| `BindingsFolder` | Folder for SteamVR bindings |
| `ActionManifestFile` | Action set used by steamvr |
| `ActionSetHandle` | Internal name used for actions |
| `ConnectedParam` | OSC parameter name set to true when AdvancedActionsOSC runs |
| `Params` | See below |
| `CustomParams` | See below |

When the program runs, it will send the parameter name specified by ConnectedParam to true. You can use that to transition to a different set of animator states when the program runs, for example, to use more complex hand gestures when available.

## Actions and Types

SteamVR actions are defined in `bindings/thumbparams_actions.json` and are used by SteamVR to bind controller actions. This program defined many actions:

### Actions
Controllers are defined by `left_xxx` and `right_xxx` action names, for example `left_a_click`.

| Action name | Description |
| --- | --- |
| `(left/right)_joystick_position` | Thumbstick position |
| `(left/right)_joystick_click` | Thumbstick click |
| `(left/right)_joystick_touch` | Thumbstick touch sensor |
| `(left/right)_trackpad_position` | Trackpad position |
| `(left/right)_trackpad_click` | Trackpad click |
| `(left/right)_trackpad_touch` | Trackpad touch sensor |
| `(left/right)_trigger_pull` | Amount the main trigger is pulled in |
| `(left/right)_trigger_touch` | Touch sensor on the main trigger |
| `(left/right)_grip_pull` | Amount the grip trigger is squeezed |
| `(left/right)_grip_force` | Force used on the grip sensor (Index Controller) |
| `(left/right)_a_click` | Lower button (A/X) pressed in |
| `(left/right)_a_touch` | Lower button (A/X) touched by thumb |
| `(left/right)_b_click` | Upper button (B/Y) pressed in |
| `(left/right)_b_touch` | Upper Button (B/Y) touched by thumb |
| `(left/right)_pose_raw` | Raw controller pose returned by SteamVR |
| `(left/right)_pose_tip` | Pose centered at the controller tip |
| `(left/right)_pose_base` | Base controller pose returned by SteamVR |
| `(left/right)_skeleton` | Controller Skeleton (not reliable on Oculus) |

Additionally, there are three actions defined for the headset

| Action name | Description |
| --- | --- |
| `head_proximity` | Proximity sensor, does not appear to work |
| `head_tap` | Tap sensing, defined in SteamVR for Oculus, but does not appear to work |
| `head_pose_raw` | Pose for the HMD, appears to be X/Z centered when the headset is woken up. Y level is relative to floor height. |

Most parameters can be remapped via the SteamVR binding menu, but default bindings are provided. It is preferred to change the configuration file rather than editing SteamVR bindings.

### Types

Boolean and float values use pythons basic data types. GLM (OpenGL Mathematics) types are used for some vectors and matrices due to the abundance of useful functions not found in libraries such as numpy.

There are five basic types for actions:

| Type | Description |
| --- | --- |
| `boolean` | Does what it says on the box |
| `vector1` | Simple float |
| `vector2` | 2d position, defined in python as a glm.vec2. Elements can be accessed via pos.x and pos.y |
| `pose` | Complex data type |
| `skeleton` | Complex data type |

Parameters fall into the types as follows:
| Parameter | Type |
| --- | --- |
| `xxx_position` | `vector2` (`glm.vec2`) |
| `xxx_click`, `xxx_touch` | `boolean` |
| `head_tap`, `head_proximity` | `boolean` |
| `xxx_pull`, `xxx_force` | `vector1` (`float`) |
| `xxx_pose_xxx` | `pose` (`DevicePose`) |
| `xxx_skeleton` | `skeleton` (`HandSkeleton`) |

Position type parameters can very between -1.0 and 1.0, _pull and _force parameters very between 0.0 and 1.0. Pose values have no limits, and skeleton splay and curl vary between 0.0 and 1.0.

### Pose Type

The pose data type is defined by the `DevicePose` class in python and has the following definition:

```python
@dataclass
class DevicePose:
    matrix : glm.mat4
    position : glm.vec3
    rotation : glm.quat
    velocity : glm.vec3
    angvelocity : glm.vec3
```

| Field | Description |
| --- | --- |
| matrix | The transform matrix as returned by SteamVR. Right handed system where +y is up, +x is right, and -z is forward.
| position | Pose position |
| rotation | Pose rotation, as a quaternion |
| velocity | Controller / HMD velocity |
| angvelocity | Controller / HMD angular velocity, expressed in radians |

All units are in metres or radians.

### Skeleton Type

The skeleton data type is relatively simple. SteamVR returns a curl value for each finger, and a splay value for each finger except the thumb. These are stored in a `HandSkeleton` data type where `skelly.fingerCurl` and `skelly.FingerSplay` are the two sets of values, respectively.

Each set of values is stored as a python list of floats with some additional attributes for handy access. Attributes are `thumb, index, middle, ring, pinky` such that values can be accessed like `skelly.fingerCurl.thumb`. Each set of values can also be accessed as a list `skelly.fingerCurl[0]`, however this syntax cannot be used for basic parameters.

Splay data does not include information for the thumb, so the data starts with index zero at the index finger.

## Basic Parameters

Basic parameters are defined under the root `Params:` key.

Parameters are set via the `ParameterName: steamvr_action_name` format, example:

```yaml
Params:
  AvatarLeftButtonATouch: left_a_touch
  AvatarLeftButtonBTouch: left_b_touch
```

Basic parameters can also access attributes of complex parameter types, for example:

```yaml
Params:
  AvatarRightThumbstickXPosition         : left_joystick.x
  AvatarHeadsetRawHeight                 : head_pose_raw.position.y
  AvatarIndexControllerRightMiddleFinger : right_skeleton.fingerCurl.middle
```

The type of each parameter is automatically determined and must be either a bool, float or an integer.

If no basic parameters are used, the config must include an empty dict: `Params: {}`

## Custom Parameters

Custom parameters are very powerful, and allow you to define arbitrary python expressions to process controller actions into a meaningful avatar parameters.

Python expressions are restricted from certain keywords and attributes, however it is not completely secure, do not use config files from people you do not trust.

Only the `math`, `numpy as np`, and `glm` imports are available to custom expressions.

Custom parameters are defined under the top level `CustomParams:` key, which is a list of actions with the following keys:

| Key | Value |
| --- | --- |
| OSCName | The avatar parameter name |
| Expression | The python expression to run |
| Actions | List of steamvr actions to expose to the python expression |

As with basic parameters, the python expression must resolve to either an integer, float, or boolean value.

Actions are passed to the python expression via the local variable `v` as a list. Some simple examples:

```yaml
CustomParams:
- OSCName: AvatarLeftThumbTouchingController
  Expression: any(v) # also could be bool(v[0] or v[1] or v[2] or v[3])
  Actions:
  - left_a_touch
  - left_b_touch
  - left_trackpad_touch
  - left_joystick_touch
- OSCName: AvatarMaxThumbstickDistanceFromCentre
  Expression: max([glm.length(d) for d in v])
  Actions:
  - left_joystick_position
  - right_joystick_position
- OSCName: ControllerTipsAreLessThan10cmApart
  Expression: glm.distance(v[0], v[1]) < 0.1
  Actions:
  - right_pose_tip.position
  - left_pose_tip.position
```

Complex expressions can produce useful parameters, the following expression computes the distance between points 20cm from the tips of the controllers:

```yaml
CustomParams:
- OSCName: ControllerTips20cmAwayDistance
  Expression: glm.distance(v[0].matrix * glm.vec4(0,0,-0.2,1), v[1].matrix * glm.vec4(0,0,-0.2,1))
  Actions:
  - right_pose_tip
  - left_pose_tip
```

If custom parameters are not used, the config file must include an empty list: `CustomParams: []`


# Avatar Setup

You will need to create avatar parameters corresponding to the names set in the configuration file.

Once avatar parameters are set on the avatar descriptor, they can be used in animator controllers.

If you use float parameters to control some motion on your avatar, you may need to use a tool such as OSCmooth to ensure other players see smooth changes to that motion, as animator parameters are not smoothed unless you have a puppet menu open for that parameter.

# Command line Arguments
You can run this by using ```AdvancedActionsOSC.exe {Arguments}``` in command line.


| Option | Value |
| ----- | ------------- |
| -d, --debug     | prints values for debugging |
| -i IP, --ip IP    | set OSC IP. Default=127.0.0.1  |
| -p PORT, --port PORT    | set OSC port. Default=9000      |
| -c FILE, --config FILE | loads configuration from the specified file. Default=config.yaml |

# Credit
- [I5UCC](https://github.com/I5UCC) for the original code and inspiration.
