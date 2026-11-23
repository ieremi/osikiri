# SayoDevice 24-Key Configuration Tool

[Japanese](README-jp.md)

A Python 3 CLI for the 24-key SayoDevice. It reads and edits key bindings over USB or in a `.sayobak` configuration file, and configures RGB lighting in configuration files. No additional Python packages are required. CLI help and error messages are in English.

Osikiri takes its name from the Japanese place name Oshikiri (押切) and also alludes to pressing a key (キーを押す).

## Command help

Use `--help` for a list of commands or place it after a command for its options.

```sh
python3 sayo24.py --help
python3 sayo24.py set --help
python3 sayo24.py set-light --help
```

## Connect over USB

USB access uses Linux `hidraw` and the legacy HID configuration protocol (Report ID `0x02`, Usage Page `0xFF00`). You need read/write access to the corresponding `/dev/hidrawN` node.

```sh
python3 sayo24.py list
python3 sayo24.py --device /dev/hidrawN read
```

Use the device path shown by `list`. You can omit `--device` if there is only one legacy configuration interface. For the `8089:0008` Left and Right units, select each device by its own path. Device numbers can change when you reconnect the units.

The `read` command lists all 24 keys in device-number order. The mapping from key numbers to physical positions depends on the model and firmware.

## Change a key binding

```sh
# Copy the layer 1 binding from key 2 to key 1
python3 sayo24.py --device /dev/hidrawN set 1 --copy-from 2 --layer 1

# Preview a shortcut on key 7
python3 sayo24.py --device /dev/hidrawN set 7 --shortcut Ctrl+Shift+F13 --dry-run

# Apply the shortcut and save it to the device
python3 sayo24.py --device /dev/hidrawN set 7 --shortcut Ctrl+Shift+F13 --save
```

`--shortcut` accepts letters, digits, F1–F24, arrow keys, and common keys such as Enter. Use Ctrl, Shift, Alt, or Gui (Windows / Command) as modifiers. Prefix a modifier with `R` for its right-hand counterpart, such as `RCtrl`.

The `read` command displays each layer as a mode byte followed by four parameter bytes in decimal. To enter a known binding directly, use `set 1 --binding MODE:P0:P1:P2:P3` with hexadecimal bytes. Their meaning depends on the firmware.

The tool reads all 24 keys before editing. When it writes a change, it reads the key back and checks the result before running `--save`. Saving commits the device’s current configuration to nonvolatile memory.

## Compatibility

Reading all 24 keys and five layers was verified on both `8089:0008` Left and Right units. The preview was also verified on hardware. Writing and saving were tested with a simulated HID device. The `list` command shows Report ID `0x21` when present. Editing requires the legacy `0x02` configuration interface.

- [sayodevice-controller, an RGB controller for a six-key SayoDevice using Report ID 0x21](https://github.com/kennedn/sayodevice-controller/blob/main/README.md)
- [Sayobot Sayo_CLI legacy HID implementation](https://github.com/Sayobot/Sayo_CLI/blob/main/o2_protocol.cpp)

## View key bindings and lighting

```sh
python3 sayo24.py --src original.sayobak show
```

The table shows all 24 keys across all five layers. Each row includes the key number, binding (mode and four hexadecimal parameter bytes), RGB color, and numeric lighting trigger. The official configurator lists effects such as Static and Breathing under Light Mode. The CLI reads the trigger value and supports continuous or press-triggered lighting settings.

### Physical key layout (Left)

This is the Left unit as shown in the official configurator with the USB icon on the right. The numbers are the `Key` values in `show`.

```text
 24   17   16    9    8    1
 23   18   15   10    7    2
 22   19   14   11    6    3     USB →
 21   20   13   12    5    4
```

The bottom-right key is `Key 4`, and its immediate left neighbor is `Key 5`. The official configurator starts counting at 0, so those positions are `Key ID 3` and `Key ID 4`, respectively.

### Physical key layout (Right)

This is the Right unit with the USB connector on the left. The numbers are the `Key` values in `show`. In the official configurator, subtract 1 to get the corresponding `Key ID`.

```text
         4    5   12   13   20   21
← USB    3    6   11   14   19   22
         2    7   10   15   18   23
         1    8    9   16   17   24
```

### How to read Binding (hex)

A binding is the action assigned to a key. The `Binding (hex)` column shows five hexadecimal bytes in the order `MODE:P0:P1:P2:P3`.

For mode `00` (standard keyboard input), `P0` is the modifier mask, `P1` is the USB HID keyboard code, and `P2` and `P3` are unused.

| Binding (hex) | Meaning |
| --- | --- |
| `00:03:68:00:00` | Ctrl+Shift+F13. The mask `03` combines Ctrl (`01`) and Shift (`02`), and `68` is F13. |
| `00:00:1C:00:00` | Y with no modifiers. The mask is `00`, and `1C` is Y. |

For other modes, the meaning of the four parameters depends on the mode.

### Key binding MODE reference

`MODE` is the first byte of a key binding. The table lists modes documented in the official guide. Availability depends on the model and firmware. [Official key binding guide](https://github.com/Sayobot/SayoDevice_manual/blob/main/docs/en/docs/std/web_hid/key.md)

| Mode | Value (decimal / hex) | Action |
| --- | --- | --- |
| Default | `0` / `00` | Sends a keyboard key with optional modifiers. |
| Keyboard | Unverified | Sends keyboard input without the Default mode's added delay. |
| Two-Step Key | Unverified | Runs separate shortcuts on press and release. |
| Tap/Hold | Unverified | Runs different actions for a tap and a hold. |
| Mouse | Unverified | Clicks, moves the cursor, or scrolls. |
| Media Controls | Unverified | Controls functions such as volume and playback. |
| Keyboard + LED Control | Unverified | Sends a shortcut and controls keyboard lock indicators. |
| A+B+C+D | Unverified | Presses up to four keys in order, then releases them together. |
| One-key Password | Unverified | Types a stored ASCII string. |
| One-key Web | Unverified | Opens a configured web address on Windows. |
| One-key Text | Unverified | Types a stored text string. |
| Shortcut ×3 | Unverified | Runs up to three shortcut steps in order. |
| Loop Input | Unverified | Repeats key inputs while held. |
| Lock Mode | Unverified | Holds a key until the next press. |
| Gamepad Button | Unverified | Sends a gamepad button input. |
| Key-to-Axis | Unverified | Maps a key to a joystick or mouse axis. |
| Num Lock Virtual Layer | Unverified | Selects an action based on Num Lock state. |
| FN Layer Switching | Unverified | Switches layers while the key is held. |
| SW Layer Switching (Set Fn Layer) | `128` / `80` | Switches layers on press and keeps the selected layer. |
| Bluetooth Device Switching | Unverified | Selects a Bluetooth device. |

On the verified 24-key Left configuration, the official configurator labels keys and layers from 0, while Osikiri starts at 1. The configurator’s `Key ID 4` on `Fn 0` is therefore `Key 5` on `Layer 1` in `show`. Its binding is `80:02:00:00:00`, matching the configurator’s **Set Fn Layer** target `fn 2`. The target uses the configurator’s zero-based numbering, so `fn 2` corresponds to Osikiri layer 3.

## Edit a .sayobak configuration file

```sh
python3 sayo24.py --src original.sayobak read
python3 sayo24.py --src original.sayobak set 7 --shortcut Ctrl+Shift+F13 --dest edited.sayobak
```

This works offline with the 24-key, five-layer layout verified in a sample .sayobak file (format 1.0). The output preserves all bytes outside the edited binding, including RGB settings. Use a new output path. The same `--copy-from`, `--binding`, and `--dry-run` options are available. Importing the edited file with the official configurator has yet to be verified.

### How to read the JSON output

The output is a JSON array with one object per key. Here is one object from that array:

```json
{
  "key": 7,
  "layers": [
    [0, 3, 104, 0, 0],
    [0, 0, 28, 0, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0]
  ]
}
```

`key` is the device key number. The entries in `layers` are ordered from layer 1 onward, so `layers[0]` is layer 1. Each entry contains `[MODE, P0, P1, P2, P3]` in decimal. In this example, layer 1 is Ctrl+Shift+F13 and layer 2 is Y. The decimal values `104` and `28` correspond to hexadecimal `68` and `1C` in the `show` table.

## Configure lighting in a .sayobak file

```sh
python3 sayo24.py --src original.sayobak read-light --layer 2
python3 sayo24.py --src original.sayobak set-light 7 --layer 2 --color FF6600 --mode static --dry-run
python3 sayo24.py --src original.sayobak set-light 7 --layer 2 --color FF6600 --mode static --dest edited.sayobak
```

Use a key number from 1 to 24 or `all`. Colors use six hexadecimal RGB digits. Use `--mode static` for continuous lighting or `--mode held` for lighting while pressed. Omit `--mode` to keep the current mode. These commands edit the configuration file offline. Restoring the edited file and checking the LEDs on hardware remain unverified.

Use `--layer 1` through `--layer 5` to select a lighting slot in the file for either command. Both commands default to layer 1. On-device behavior for layers 2–5 has yet to be verified.

### Light Mode and trigger values

In the official configurator, **Light Mode** selects the lighting effect. The table lists the available effects and the known file codes. The captured Static report uses effect code `0`. The other effect codes are unverified. [Official lighting guide](https://github.com/Sayobot/SayoDevice_manual/blob/main/docs/en/docs/std/web_hid/led.md) · [Captured Static report](https://github.com/kennedn/sayodevice-controller/blob/main/README.md#protocol)

| Light Mode | File code | Effect |
| --- | --- | --- |
| Static | `0` | Steady light, controlled by the trigger |
| Indicator | Unverified | Shows Num Lock, Caps Lock, or Scroll Lock status |
| Breathing | Unverified | Repeatedly brightens and dims |
| Breathing Once | Unverified | Runs one breathing cycle on a trigger |
| Wave | Unverified | Animates colors in a non-static color mode |
| Switch | Unverified | Cycles colors at a set interval |
| Switch Once | Unverified | Advances the color on a trigger |
| Blink | Unverified | Flashes at set on/off intervals |
| Blink Once | Unverified | Flashes on a trigger |
| Fade out | Unverified | Gradually turns off on a trigger |
| Fade in | Unverified | Gradually turns on on a trigger |

`show` displays the **Light trigger** value. `read-light` exposes the same value as `mode` in JSON. The CLI's `set-light --mode` option changes this trigger.

| Trigger value | CLI option | When a Static light is on |
| --- | --- | --- |
| `0` | `--mode static` | Continuously |
| `1` | `--mode held` | While the key is pressed |
