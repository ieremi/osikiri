# SayoDevice 24-Key Configuration Tool

[日本語](README-jp.md)

A Python 3 CLI for reading and editing key bindings on a 24-key SayoDevice through Linux `hidraw`. It uses the legacy HID configuration protocol (Report ID `0x02`, Usage Page `0xFF00`). You need a USB connection and read/write access to the corresponding `/dev/hidrawN` node. No additional Python packages are required.

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

## Edit a .sayobak backup

```sh
python3 sayo24.py --backup original.sayobak read
python3 sayo24.py --backup original.sayobak set 7 --shortcut Ctrl+Shift+F13 --output edited.sayobak
```

This works offline with the 24-key, five-layer layout verified in a Sayo Device Backup File 1.0 sample. The output preserves all bytes outside the edited binding, including RGB settings. Use a new output path. The same `--copy-from`, `--binding`, and `--dry-run` options are available. Importing the edited file with the official configurator has yet to be verified.
