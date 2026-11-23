# SayoDevice 24-Key Configuration Tool

[Japanese](README-jp.md)

A Python 3 CLI for the 24-key SayoDevice. It reads and edits key bindings over USB or in a `.sayobak` configuration file, and configures RGB lighting in configuration files. No additional Python packages are required. CLI help and error messages are in English.

Osikiri takes its name from the Japanese place name Oshikiri (押切) and also alludes to pressing a key (キーを押す).

## Configuration commands

| Direction | Command |
| --- | --- |
| Device → files | `pull` |
| Binary file → device | `push` |
| Text → binary | `encode` |
| Binary → text | `decode` |

## Command help

Write the subcommand first, followed by its options. Use `--help` for a list of commands or place it after a command for its options.

```sh
./osikiri --help
./osikiri set --help
./osikiri set-light --help
```

## Connect over USB

USB access uses Linux `hidraw` and the legacy HID configuration protocol (Report ID `0x02`, Usage Page `0xFF00`). You need read/write access to the corresponding `/dev/hidrawN` node.

```sh
./osikiri list
./osikiri read --device /dev/hidrawN
```

Use the device path shown by `list`. You can omit `--device` if there is only one legacy configuration interface. For the `8089:0008` Left and Right units, select each device by its own path. Device numbers can change when you reconnect the units.

The `read` command lists all 24 keys in device-number order. The mapping from key numbers to physical positions depends on the model and firmware.

### How to read the JSON output (USB device)

The output is a JSON array with one object per key. Here is one object from that array:

```json
{
  "key": 6,
  "layers": [
    [0, 3, 104, 0, 0],
    [0, 0, 28, 0, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0]
  ]
}
```

`key` is the device key number. The entries in `layers` are indexed by Fn layer, so `layers[0]` is Fn 0. Each entry contains `[MODE, P0, P1, P2, P3]` in decimal. In this example, Fn 0 is Ctrl+Shift+F13 and Fn 1 is Y. The decimal values `104` and `28` correspond to hexadecimal `68` and `1C` in the `show` table.

## Change a key binding

```sh
# Copy the Fn 0 binding from key ID 1 to key ID 0
./osikiri set --device /dev/hidrawN 0 --copy-from 1 --layer 0

# Preview a shortcut on key ID 6
./osikiri set --device /dev/hidrawN 6 --shortcut Ctrl+Shift+F13 --dry-run

# Apply the shortcut and save it to the device
./osikiri set --device /dev/hidrawN 6 --shortcut Ctrl+Shift+F13 --save
```

`--shortcut` accepts letters, digits, F1–F24, arrow keys, and common keys such as Enter. Use Ctrl, Shift, Alt, or Gui (Windows / Command) as modifiers. Prefix a modifier with `R` for its right-hand counterpart, such as `RCtrl`.

The `read` command displays each layer as a mode byte followed by four parameter bytes in decimal. To enter a known binding directly, use `set 0 --binding MODE:P0:P1:P2:P3` with hexadecimal bytes. Their meaning depends on the firmware.

The tool reads all 24 keys before editing. When it writes a change, it reads the key back and checks the result before running `--save`. Saving commits the device’s current configuration to nonvolatile memory.

## Compatibility

Reading all 24 keys and five layers was verified on both `8089:0008` Left and Right units. The preview was also verified on hardware. Writing and saving were tested with a simulated HID device. The `list` command shows Report ID `0x21` when present. Editing requires the legacy `0x02` configuration interface.

- [sayodevice-controller, an RGB controller for a six-key SayoDevice using Report ID 0x21](https://github.com/kennedn/sayodevice-controller/blob/main/README.md)
- [Sayobot Sayo_CLI legacy HID implementation](https://github.com/Sayobot/Sayo_CLI/blob/main/o2_protocol.cpp)

## View key bindings and lighting

```sh
./osikiri show --src original.sayobak
```

The table shows key IDs 0–23 and Fn layers 0–4, matching the official configurator. CLI arguments and JSON key IDs use the same numbering. If you used an earlier release, subtract 1 from its key and layer arguments. Each row includes the key number, binding (mode and four hexadecimal parameter bytes), RGB color, and numeric lighting trigger. The official configurator lists effects such as Static and Breathing under Light Mode. The CLI reads the trigger value and supports continuous or press-triggered lighting settings.

### Physical key layout (Left)

This is the Left unit as shown in the official configurator with the USB icon on the right. The numbers match the `Key ID` values in both `show` and the official configurator.

```text
 23   16   15    8    7    0
 22   17   14    9    6    1
 21   18   13   10    5    2     USB →
 20   19   12   11    4    3
```

The bottom-right key is `Key ID 3`, and its immediate left neighbor is `Key ID 4`.

### Physical key layout (Right)

This is the Right unit with the USB connector on the left. The numbers match the `Key ID` values in both `show` and the official configurator.

```text
         3    4   11   12   19   20
← USB    2    5   10   13   18   21
         1    6    9   14   17   22
         0    7    8   15   16   23
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

On the Left unit, `Key ID 4` on Fn 0 has the binding `80:02:00:00:00`, which sets the active layer to Fn 2.

## Edit a .sayobak configuration file

```sh
./osikiri set --src original.sayobak 6 --shortcut Ctrl+Shift+F13 --dest out
```

This works offline with the 24-key, five-layer layout verified in a sample .sayobak file (format 1.0). The output preserves all bytes outside the edited binding, including RGB settings. Use `--dest` to select the output directory. The same `--copy-from`, `--binding`, and `--dry-run` options are available. Importing the edited file with the official configurator has yet to be verified.

## Configure lighting in a .sayobak file

```sh
./osikiri read-light --src original.sayobak --layer 1
./osikiri set-light --src original.sayobak 6 --layer 1 --color FF6600 --mode static --dry-run
./osikiri set-light --src original.sayobak 6 --layer 1 --color FF6600 --mode static --dest out
```

Use a key ID from 0 to 23 or `all`. Colors use six hexadecimal RGB digits. Use `--mode static` for continuous lighting or `--mode held` for lighting while pressed. Omit `--mode` to keep the current mode. These commands edit the configuration file offline. Restoring the edited file and checking the LEDs on hardware remain unverified.

Use `--layer 0` through `--layer 4` to select a lighting slot in the file for either command. Both commands default to Fn 0. On-device behavior for Fn 1–4 has yet to be verified.

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

## Synchronize the device and configuration files

```sh
./osikiri pull
./osikiri pull /dev/hidrawN
./osikiri pull --device /dev/hidrawN --dest out
./osikiri push --device /dev/hidrawN --src out/SayoDevice-Left-2026-11-23-12-00-00.sayobak --dry-run
./osikiri push --device /dev/hidrawN --src out/SayoDevice-Left-2026-11-23-12-00-00.sayobak --apply --save
```

`pull` reads all 24 keys and five Fn layers, including RGB lighting, over HID Report ID `0x21`. The device is the sole input. With no device path, `pull` reads all connected compatible devices. To read a single device, pass its HID path directly or with `--device`. The command prints the device name and path before writing its files. Osikiri waits for a reply matching the requested record when the device sends unrelated HID reports. The generated `.sayobak` contains only the key bindings and lighting records read by Osikiri. Scripts and color tables are outside this export. Importing this partial file in the official configurator has yet to be verified. `push` applies only key bindings and lighting from the binary file, verifies each changed record, and optionally saves successful changes to nonvolatile memory. If a write fails partway through, the live settings may reflect the records written before the failure.

Whenever a command writes a binary `.sayobak` file, it also writes a same-name `.json` file with editable JSON. Output names use local time in 24-hour format, `yyyy-MM-dd-hh-mm-ss.json` and `yyyy-MM-dd-hh-mm-ss.sayobak`. Both files in a pair share the same timestamp. For `pull`, the device name comes before the timestamp, with spaces and filename separators replaced by hyphens. For example, `SayoDevice-Left-2026-11-23-12-00-00.sayobak`. If a name is already in use, the tool advances the timestamp by one second until it finds an available name. `--dest` selects the output directory and defaults to `out/`. The tool creates the directory if needed and prints the generated paths. Use those paths in subsequent commands.

## Convert between text and binary

```sh
./osikiri decode original.sayobak --dest out
./osikiri encode --src out/2026-11-23-12-00-00.json --dest out
```

Pass the source file directly to `decode` or specify it with `--src`.

Each `keys[].id` identifies the key for all its layers. Each `lighting` object contains only `color` and `mode`. Edit `keys[].layers[].binding` in `MODE:P0:P1:P2:P3` hexadecimal format and `lighting.color` or `lighting.mode` for RGB and trigger settings.

When you run `encode`, the JSON values for `binding`, `lighting.color`, and `lighting.mode` take precedence over the corresponding values in `source_binary`. For example, if the embedded binary assigns Y but the JSON specifies `00:03:68:00:00`, the output assigns Ctrl+Shift+F13.

The embedded `source_binary` preserves the original data outside these fields, including scripts and color tables. Keep it intact. An unchanged text file encodes to a byte-identical binary.
