#!/usr/bin/env python3
"""Inspect and edit 24-key SayoDevice bindings over HID or in a .sayobak configuration file."""

import argparse
import base64
import binascii
import fcntl
import json
import os
from pathlib import Path
import re
import select
import struct
import sys
import tempfile
import time
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta

KEY_COUNT = 24
REPORT_SIZE = 64
REPORT_ID = 2
KEY_MAP = 0x16
HEADER_SIZE = 16
LAYER_SIZE = 6
MAX_LAYERS = 5
SYSFS = Path("/sys/class/hidraw")
OUTPUT_DIR = Path("out")
SAYOBAK_MAGIC = b"Sayo Device Backup File 1.0".ljust(64, b"\0")
SAYOBAK_RECORD_START = 0x69
SAYOBAK_RECORD = struct.Struct("<BBI")
SAYOBAK_LAYER_SIZE = 8
SAYOBAK_KEY_COMMAND = 0x10
SAYOBAK_LIGHT_COMMAND = 0x11
SAYOBAK_LIGHT_RGB_OFFSET = 20
SAYOBAK_LIGHT_MODE_OFFSET = 17
SAYOBAK_RECORD_SIZE = HEADER_SIZE + MAX_LAYERS * SAYOBAK_LAYER_SIZE
V2_REPORT_ID = 0x21
V2_HEADER = struct.Struct("<BBHHBB")
V2_WORDS = struct.Struct("<32H")
KEY_CODES = {
    **{chr(65 + i): 4 + i for i in range(26)},
    **{key: 30 + i for i, key in enumerate("1234567890")},
    **{f"F{i}": 57 + i for i in range(1, 13)},
    **{f"F{i}": 91 + i for i in range(13, 25)},
    "NONE": 0, "ENTER": 40, "ESC": 41, "BACKSPACE": 42, "TAB": 43,
    "SPACE": 44, "DELETE": 76, "RIGHT": 79, "LEFT": 80, "DOWN": 81, "UP": 82,
}
MODIFIERS = {
    name: 1 << bit for bit, name in enumerate(
        ("CTRL", "SHIFT", "ALT", "GUI", "RCTRL", "RSHIFT", "RALT", "RGUI")
    )
}


def devices():
    for entry in sorted(SYSFS.glob("hidraw*")):
        try:
            info = dict(line.split("=", 1) for line in
                        (entry / "device/uevent").read_text().splitlines() if "=" in line)
            bus, vendor, product = (int(part, 16) for part in info["HID_ID"].split(":"))
            descriptor = (entry / "device/report_descriptor").read_bytes()
        except (OSError, KeyError, ValueError):
            continue
        if bus == 3 and vendor == 0x8089:
            yield Path("/dev") / entry.name, product, info.get("HID_NAME", ""), descriptor


def write_output(directory, document, binary=None, *, prefix=""):
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().replace(microsecond=0)
    with tempfile.TemporaryDirectory(dir=directory) as staging:
        text = Path(staging) / "settings.json"
        text.write_text(document, encoding="utf-8")
        if binary is not None:
            data = Path(staging) / "settings.sayobak"
            data.write_bytes(binary)
        while True:
            stem = prefix + timestamp.strftime("%Y-%m-%d-%H-%M-%S")
            text_path = directory / f"{stem}.json"
            binary_path = directory / f"{stem}.sayobak"
            try:
                os.link(text, text_path)
            except FileExistsError:
                timestamp += timedelta(seconds=1)
                continue
            try:
                if binary is not None:
                    os.link(data, binary_path)
                elif binary_path.exists():
                    raise FileExistsError(binary_path)
            except OSError as exc:
                text_path.unlink()
                if isinstance(exc, FileExistsError):
                    timestamp += timedelta(seconds=1)
                    continue
                raise
            break
    if binary is not None:
        print(f"Wrote {binary_path}", file=sys.stderr)
    print(f"Wrote {text_path}", file=sys.stderr)


def packet(command, payload):
    prefix = bytes((REPORT_ID, command, len(payload))) + payload
    return (prefix + bytes((sum(prefix) & 0xff,))).ljust(REPORT_SIZE, b"\0")


class Device:
    def __init__(self, fd):
        self.fd = fd

    def report(self, frame, report_id, timeout, record_id=None):
        if os.write(self.fd, frame) != len(frame):
            raise ValueError("Could not send the complete HID report.")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not select.select([self.fd], [], [], max(0, deadline - time.monotonic()))[0]:
                break
            reply = os.read(self.fd, REPORT_SIZE)
            if not reply:
                raise ValueError("The HID device stopped responding.")
            if reply[0] != report_id:
                continue
            if len(reply) != REPORT_SIZE:
                raise ValueError("Unexpected HID response format.")
            if record_id is None or V2_HEADER.unpack_from(reply)[-2:] == record_id:
                return reply
        if record_id is not None:
            command, index = record_id
            raise ValueError(f"No matching response for record 0x{command:02x}, key ID {index}.")
        raise ValueError("No response to the HID request.")

    def exchange(self, command, payload, timeout=1):
        reply = self.report(packet(command, payload), REPORT_ID, timeout)
        if len(reply) != REPORT_SIZE or reply[2] > 60:
            raise ValueError("Unexpected HID response format.")
        if reply[1]:
            raise ValueError(f"Device rejected command 0x{command:02x} (status 0x{reply[1]:02x}).")
        return reply[3:3 + reply[2]]

    def read_key(self, index):
        payload = self.exchange(KEY_MAP, bytes((0, index)))
        extra = len(payload) - HEADER_SIZE
        if (extra not in range(LAYER_SIZE, (MAX_LAYERS + 1) * LAYER_SIZE, LAYER_SIZE)
                or payload[1] != index):
            raise ValueError(f"Unexpected response format for key {index}.")
        return payload

    def write_key(self, index, payload):
        self.exchange(KEY_MAP, bytes((1,)) + payload[1:])
        if self.read_key(index)[HEADER_SIZE:] != payload[HEADER_SIZE:]:
            raise ValueError("The binding read back from the device differs from the requested binding.")

    def save(self):
        self.exchange(4, bytes.fromhex("72 96"), timeout=2)

    def record(self, command, index, payload=b""):
        frame = bytearray(REPORT_SIZE)
        V2_HEADER.pack_into(frame, 0, V2_REPORT_ID, 3, 0, len(payload) + 4, command, index)
        frame[V2_HEADER.size:V2_HEADER.size + len(payload)] = payload
        struct.pack_into("<H", frame, 2, sum(V2_WORDS.unpack(frame)) & 0xffff)
        reply = self.report(frame, V2_REPORT_ID, 1, (command, index))
        _, _, checksum, length, _, _ = V2_HEADER.unpack_from(reply)
        expected_checksum = (sum(V2_WORDS.unpack(reply)) - checksum) & 0xffff
        if (length not in ((4, 60) if payload else (60,))
                or expected_checksum != checksum):
            raise ValueError(f"Invalid response for record 0x{command:02x}, key ID {index}.")
        return reply[V2_HEADER.size:]


class SayoFile:
    def __init__(self, data):
        self.data = bytearray(data)
        end = len(self.data)
        if not self.data.startswith(SAYOBAK_MAGIC):
            raise ValueError("Unsupported .sayobak configuration file format.")

        self.keys = {}
        self.lights = {}
        # Osikiri device exports place records immediately after the magic.
        first_record = SAYOBAK_RECORD.pack(SAYOBAK_KEY_COMMAND, 0, SAYOBAK_RECORD_SIZE)
        offset = SAYOBAK_RECORD_START
        if self.data.startswith(first_record, len(SAYOBAK_MAGIC)):
            offset = len(SAYOBAK_MAGIC)
        while offset < end:
            if end - offset < SAYOBAK_RECORD.size:
                raise ValueError("The configuration file contains a truncated record header.")
            command, index, size = SAYOBAK_RECORD.unpack_from(self.data, offset)
            payload = offset + SAYOBAK_RECORD.size
            offset = payload + size
            if offset > end:
                raise ValueError("The configuration file contains a truncated record.")
            if command == SAYOBAK_KEY_COMMAND:
                if index in self.keys or size != SAYOBAK_RECORD_SIZE:
                    raise ValueError("Invalid key binding record in the configuration file.")
                self.keys[index] = payload + HEADER_SIZE
            elif command == SAYOBAK_LIGHT_COMMAND:
                if index in self.lights or size != SAYOBAK_RECORD_SIZE:
                    raise ValueError("Invalid lighting record in the configuration file.")
                self.lights[index] = payload
        if self.keys.keys() != set(range(KEY_COUNT)):
            raise ValueError("The configuration file must contain bindings for all 24 keys.")

    @classmethod
    def load(cls, path):
        return cls(path.read_bytes())

    def to_text(self):
        keys = [self.read_key(index) for index in range(KEY_COUNT)]
        lights_by_layer = [
            {
                light["key"]: {"color": light["color"], "mode": light["mode"]}
                for light in self.lighting(self.lights, layer)
            }
            for layer in range(MAX_LAYERS)
        ]
        config = {
            "format": "osikiri-1",
            "keys": [
                {
                    "id": index,
                    "layers": [
                        {
                            "binding": binding(key, layer).hex(":").upper(),
                            "lighting": lights_by_layer[layer].get(index),
                        }
                        for layer in range(MAX_LAYERS)
                    ],
                }
                for index, key in enumerate(keys)
            ],
            "source_binary": base64.b64encode(self.data).decode("ascii"),
        }
        return json.dumps(config, indent=2) + "\n"

    @classmethod
    def from_text(cls, path):
        config = json.loads(path.read_text(encoding="utf-8"))
        try:
            if config["format"] != "osikiri-1":
                raise ValueError("Unsupported text configuration format.")
            settings = cls(base64.b64decode(config["source_binary"], validate=True))
            keys = config["keys"]
            if [key["id"] for key in keys] != list(range(KEY_COUNT)):
                raise ValueError("Expected key IDs 0-23 in order.")
            for index, key in enumerate(keys):
                layers = key["layers"]
                if len(layers) != MAX_LAYERS:
                    raise ValueError(f"Expected five layers for key ID {index}.")
                payload = bytearray(settings.read_key(index))
                for layer, entry in enumerate(layers):
                    values = parse_binding(entry["binding"])
                    offset = layer_offset(payload, layer)
                    payload[offset] = values[0]
                    payload[offset + 2:offset + LAYER_SIZE] = values[1:]
                    if index in settings.lights:
                        light = entry["lighting"]
                        if type(light["mode"]) is not int or not 0 <= light["mode"] <= 255:
                            raise ValueError(f"Invalid lighting trigger for key ID {index}, layer {layer}.")
                        settings.lighting((index,), layer, parse_color(light["color"]), light["mode"])
                    elif entry["lighting"] is not None:
                        raise ValueError(f"The source has no lighting record for key ID {index}.")
                settings.write_key(index, payload)
            return settings
        except (KeyError, TypeError, argparse.ArgumentTypeError, binascii.Error) as exc:
            raise ValueError(f"Invalid text configuration: {exc}") from exc

    def read_key(self, index):
        # Convert to the CLI's legacy key layout. The file stores three
        # additional bytes between the mode and the four parameters.
        start = self.keys[index]
        payload = bytearray(HEADER_SIZE)
        payload[1] = index
        for offset in range(start, start + MAX_LAYERS * SAYOBAK_LAYER_SIZE, SAYOBAK_LAYER_SIZE):
            payload.extend((self.data[offset], 0))
            payload.extend(self.data[offset + 4:offset + 8])
        return bytes(payload)

    def write_key(self, index, payload):
        for layer in range(MAX_LAYERS):
            offset = self.keys[index] + layer * SAYOBAK_LAYER_SIZE
            values = binding(payload, layer)
            self.data[offset] = values[0]
            self.data[offset + 4:offset + 8] = values[1:]

    def export(self, directory, *, prefix=""):
        write_output(directory, self.to_text(), self.data, prefix=prefix)

    def summary(self):
        rows = ["Layer  Key ID  Binding (hex)   RGB      Light trigger"]
        keys = [self.read_key(index) for index in range(KEY_COUNT)]
        for layer in range(MAX_LAYERS):
            for index, key in enumerate(keys):
                values = binding(key, layer).hex(":").upper()
                light = self.lighting((index,), layer)[0] if index in self.lights else None
                color = light["color"].upper() if light else "-"
                trigger = str(light["mode"]) if light else "-"
                rows.append(f"{layer:>5}  {index:>6}  {values}  {color:<7}  {trigger:>13}")
        return "\n".join(rows)

    def device_records(self):
        if self.lights.keys() != self.keys.keys():
            raise ValueError("Synchronization requires one lighting record per key.")
        for command, offsets in ((SAYOBAK_KEY_COMMAND, self.keys),
                                 (SAYOBAK_LIGHT_COMMAND, self.lights)):
            for index in range(KEY_COUNT):
                slots = offsets[index] + (HEADER_SIZE if command == SAYOBAK_LIGHT_COMMAND else 0)
                yield command, index, slots

    def lighting(self, indices, layer, color=None, mode=None):
        if any(index not in self.lights for index in indices):
            raise ValueError("No lighting record for one or more selected keys.")
        result = []
        for index in indices:
            payload = self.lights[index] + layer * SAYOBAK_LAYER_SIZE
            rgb = payload + SAYOBAK_LIGHT_RGB_OFFSET
            mode_offset = payload + SAYOBAK_LIGHT_MODE_OFFSET
            if color is not None:
                self.data[rgb:rgb + 3] = color
            if mode is not None:
                self.data[mode_offset] = mode
            result.append({
                "key": index,
                "color": "#" + self.data[rgb:rgb + 3].hex(),
                "mode": self.data[mode_offset],
            })
        return result


def pull_settings(args):
    candidates = configuration_interfaces(args.device, v2=True)
    if not candidates:
        raise ValueError("No matching HID v2 configuration interface. Run list to see available devices.")
    for path, name in candidates:
        print(f"Reading {name} ({path})", file=sys.stderr)
        data = bytearray(SAYOBAK_MAGIC)
        with open_interface(path) as device:
            for command in (SAYOBAK_KEY_COMMAND, SAYOBAK_LIGHT_COMMAND):
                for index in range(KEY_COUNT):
                    record = device.record(command, index)
                    data.extend(SAYOBAK_RECORD.pack(command, index, len(record)))
                    data.extend(record)
        filename_name = re.sub(r"[^\w-]+", "-", name)[:48].strip("-_") or path.name
        SayoFile(data).export(args.dest, prefix=f"{filename_name}-")


def push_settings(args):
    settings = SayoFile.load(args.src)
    changes = []
    with open_device(args.device) as device:
        for command, index, start in settings.device_records():
            current = device.record(command, index)
            desired = settings.data[start:start + MAX_LAYERS * SAYOBAK_LAYER_SIZE]
            if current[HEADER_SIZE:] != desired:
                changes.append((command, index, current, current[:HEADER_SIZE] + desired))

        if not args.dry_run:
            for command, index, current, desired in changes:
                if device.record(command, index) != current:
                    raise ValueError(f"Device record changed during synchronization for key ID {index}.")
                device.record(command, index, desired)
                if device.record(command, index) != desired:
                    raise ValueError(f"Device record readback differs for key ID {index}.")
            if args.save and changes:
                device.save()
    for command, index, _, _ in changes:
        print(f"Key ID {index}: {'binding' if command == SAYOBAK_KEY_COMMAND else 'lighting'}")
    print(f"{len(changes)} {'records would change' if args.dry_run else 'records changed'}.")

def configuration_interfaces(path, *, v2=False):
    usage_page, report = (b"\x06\x11\xff", b"\x85\x21") if v2 else (b"\x06\x00\xff", b"\x85\x02")
    return [
        (node, name) for node, _, name, desc in devices()
        if "boot" not in name.casefold() and usage_page in desc
        and report in desc and (path is None or path == node)
    ]


def open_device(path):
    candidates = configuration_interfaces(path)
    if len(candidates) != 1:
        raise ValueError("Could not select a single legacy HID configuration interface. Run list to see available devices.")
    return open_interface(candidates[0][0])


@contextmanager
def open_interface(path):
    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield Device(fd)
    finally:
        os.close(fd)


def layer_offset(payload, layer):
    offset = HEADER_SIZE + layer * LAYER_SIZE
    if layer < 0 or offset + LAYER_SIZE > len(payload):
        raise ValueError(f"Layer {layer} is unavailable for this key.")
    return offset


def binding(payload, layer):
    offset = layer_offset(payload, layer)
    return payload[offset:offset + 1] + payload[offset + 2:offset + LAYER_SIZE]


def describe(payload):
    return {
        "key": payload[1],
        "layers": [
            list(binding(payload, layer))
            for layer in range((len(payload) - HEADER_SIZE) // LAYER_SIZE)
        ],
    }


def parse_binding(value):
    try:
        result = bytes(int(part, 16) for part in value.split(":"))
        if len(result) == 5:
            return result
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("Enter five hexadecimal bytes separated by colons.")


def parse_shortcut(value):
    *modifiers, key = value.upper().split("+")
    try:
        mask = sum(MODIFIERS[modifier] for modifier in set(modifiers))
        return bytes((0, mask, KEY_CODES[key], 0, 0))
    except KeyError as exc:
        raise argparse.ArgumentTypeError(f"Unsupported key name: {exc.args[0]}") from exc


def parse_color(value):
    if not re.fullmatch(r"#?[0-9a-fA-F]{6}", value):
        raise argparse.ArgumentTypeError("Enter a color in RRGGBB format.")
    return bytes.fromhex(value.removeprefix("#"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", type=Path, help="Target /dev/hidrawN device")
    parser.add_argument("--src", type=Path, help="Input .sayobak configuration file")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List SayoDevice HID interfaces",
                        description="Show detected HID paths, USB IDs, and configuration report IDs.")
    commands.add_parser("read", help="Print bindings for all 24 keys as JSON",
                        description="Read bindings directly from a USB device.",
                        epilog="Example: python3 sayo24.py read --device /dev/hidrawN")
    commands.add_parser(
        "show", help="Show key bindings and RGB lighting for every layer",
        description="Display the bindings and lighting in a .sayobak file.",
        epilog="Example: python3 sayo24.py show --src settings.sayobak",
    )
    pull = commands.add_parser(
        "pull", help="Read device bindings and lighting into a file pair",
        description="Read all connected compatible devices unless --device selects one.",
        epilog="Example: python3 sayo24.py pull /dev/hidrawN",
    )
    pull.add_argument("device_path", nargs="?", type=Path, metavar="DEVICE",
                      help="Target /dev/hidrawN device")
    pull.add_argument("--dest", type=Path, default=OUTPUT_DIR, help="Output directory (default: out)")
    push = commands.add_parser("push", help="Apply bindings and lighting from a .sayobak file")
    push_action = push.add_mutually_exclusive_group(required=True)
    push_action.add_argument("--dry-run", action="store_true", help="List records that would change")
    push_action.add_argument("--apply", action="store_true", help="Write and verify changed records")
    push.add_argument("--save", action="store_true", help="Save applied changes to nonvolatile memory")
    encode = commands.add_parser("encode", help="Convert editable JSON to a .sayobak file pair")
    encode.add_argument("--dest", type=Path, default=OUTPUT_DIR, help="Output directory (default: out)")
    decode = commands.add_parser("decode", help="Convert a .sayobak file to editable JSON")
    decode.add_argument("--dest", type=Path, default=OUTPUT_DIR, help="Output directory (default: out)")
    read_light = commands.add_parser(
        "read-light", help="Show RGB lighting for all 24 keys in the configuration file",
        description="Read lighting for one layer in a .sayobak file.",
        epilog="Example: python3 sayo24.py read-light --src settings.sayobak --layer 1",
    )
    light = commands.add_parser(
        "set-light", help="Edit RGB lighting in the configuration file",
        description="Change lighting for one layer in a .sayobak file.",
        epilog="Example: python3 sayo24.py set-light --src settings.sayobak all --color 00BFFF --dry-run",
    )
    light.add_argument("key", choices=[str(key) for key in range(KEY_COUNT)] + ["all"],
                       metavar="KEY|all", help="Key ID (0-23), or all keys")
    light.add_argument("--color", type=parse_color, required=True, metavar="RRGGBB",
                       help="Six hexadecimal RGB digits, optionally prefixed with #")
    light.add_argument("--mode", choices=("static", "held"), help="Light continuously or only while pressed")
    for lighting_command in (read_light, light):
        lighting_command.add_argument("--layer", type=int, choices=range(MAX_LAYERS),
                                      default=0, help="Lighting layer (default: 0)")
    light_destination = light.add_mutually_exclusive_group()
    light_destination.add_argument("--dest", type=Path, help="Output directory (default: out)")
    light_destination.add_argument("--dry-run", action="store_true", help="Preview the lighting changes")
    edit = commands.add_parser(
        "set", help="Edit the binding for one key on one layer",
        description="Edit a USB device or use --src to edit a .sayobak file.",
        epilog="Example: python3 sayo24.py set --src settings.sayobak 6 --shortcut Ctrl+Shift+F13 --dry-run",
    )
    edit.add_argument("key", type=int, choices=range(KEY_COUNT), metavar="KEY",
                      help="Key ID (0-23)")
    edit.add_argument("--layer", type=int, choices=range(MAX_LAYERS), default=0,
                      help="Binding layer (default: 0)")
    source = edit.add_mutually_exclusive_group(required=True)
    source.add_argument("--copy-from", type=int, choices=range(KEY_COUNT), metavar="KEY",
                        help="Copy another key's binding from the selected layer")
    source.add_argument("--binding", type=parse_binding, metavar="MODE:P0:P1:P2:P3",
                        help="Enter the binding as five hexadecimal bytes")
    source.add_argument("--shortcut", type=parse_shortcut, metavar="CTRL+SHIFT+F13",
                        help="Assign a key with optional modifiers")
    edit.add_argument("--dry-run", action="store_true", help="Preview the binding change")
    destination = edit.add_mutually_exclusive_group()
    destination.add_argument("--save", action="store_true", help="Save to the device nonvolatile memory")
    destination.add_argument("--dest", type=Path, help="Output directory for file edits (default: out)")
    # Suppressed defaults keep values supplied before the subcommand.
    for command in ("read", "set", "pull", "push"):
        commands.choices[command].add_argument(
            "--device", type=Path, default=argparse.SUPPRESS, help="Target /dev/hidrawN device",
        )
    for command in ("show", "read-light", "set-light", "set", "push", "decode", "encode"):
        commands.choices[command].add_argument(
            "--src", type=Path, default=argparse.SUPPRESS, help="Input configuration file",
        )
    args = parser.parse_args(argv)
    if args.command == "pull" and args.device_path is not None:
        if args.device is not None:
            parser.error("Specify the pull device as a positional argument or with --device.")
        args.device = args.device_path
    if args.command == "pull" and args.src:
        parser.error("pull reads from the device and does not accept --src.")
    if args.command == "push":
        if not args.src:
            parser.error("push requires --src.")
        if args.save and not args.apply:
            parser.error("--save requires --apply.")
    elif args.device and args.src:
        parser.error("--device and --src can only be combined for push.")
    if args.command in ("encode", "decode") and (not args.src or args.device):
        parser.error(f"{args.command} requires --src and does not use a USB device.")
    if args.command == "list" and args.src:
        parser.error("list does not accept --src.")
    if args.command == "read" and args.src:
        parser.error("Use show with --src to display a configuration file.")
    if args.command == "show" and not args.src:
        parser.error("show requires --src.")
    if args.command in ("read-light", "set-light") and not args.src:
        parser.error("Lighting commands require --src.")
    if args.command == "set":
        if args.dry_run and (args.save or args.dest):
            parser.error("--dry-run cannot be combined with --save or --dest.")
        if args.src and args.save:
            parser.error("--save is only available when editing a USB device.")
        if args.dest and not args.src:
            parser.error("--dest requires --src.")

    try:
        if args.command == "pull":
            pull_settings(args)
            return 0
        if args.command == "push":
            push_settings(args)
            return 0
        if args.command == "encode":
            SayoFile.from_text(args.src).export(args.dest)
            return 0
        if args.command == "decode":
            write_output(args.dest, SayoFile.load(args.src).to_text())
            return 0
        if args.command == "show":
            print(SayoFile.load(args.src).summary())
            return 0
        if args.command == "read-light":
            print(json.dumps(SayoFile.load(args.src).lighting(range(KEY_COUNT), args.layer), indent=2))
            return 0
        if args.command == "set-light":
            settings = SayoFile.load(args.src)
            indices = range(KEY_COUNT) if args.key == "all" else [int(args.key)]
            mode = {"static": 0, "held": 1}.get(args.mode)
            result = settings.lighting(indices, args.layer, args.color, mode)
            if not args.dry_run:
                settings.export(args.dest or OUTPUT_DIR)
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "list":
            for node, pid, name, desc in devices():
                reports = [f"0x{rid:02x}" for rid in (2, 0x21) if bytes((0x85, rid)) in desc]
                print(f"{node} 8089:{pid:04x} {name} (report {', '.join(reports) or '-'})")
            return 0

        target = nullcontext(SayoFile.load(args.src)) if args.src else open_device(args.device)
        with target as device:
            keys = [device.read_key(index) for index in range(KEY_COUNT)]
            if args.command == "read":
                print(json.dumps([describe(key) for key in keys], indent=2))
                return 0

            index = args.key
            current = keys[index]
            offset = layer_offset(current, args.layer)
            new_binding = args.binding or args.shortcut
            if args.copy_from is not None:
                new_binding = binding(keys[args.copy_from], args.layer)
            updated = bytearray(current)
            updated[offset] = new_binding[0]
            updated[offset + 2:offset + LAYER_SIZE] = new_binding[1:]
            if not args.dry_run and updated != current:
                device.write_key(index, bytes(updated))
            if args.save:
                device.save()
            if args.src and not args.dry_run:
                device.export(args.dest or OUTPUT_DIR)
            print(json.dumps(describe(updated)))
        return 0
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
