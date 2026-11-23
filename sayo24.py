#!/usr/bin/env python3
"""Inspect and edit 24-key SayoDevice bindings over HID or in a backup file."""

import argparse
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

KEY_COUNT = 24
REPORT_SIZE = 64
REPORT_ID = 2
KEY_MAP = 0x16
HEADER_SIZE = 16
LAYER_SIZE = 6
MAX_LAYERS = 5
SYSFS = Path("/sys/class/hidraw")
BACKUP_MAGIC = b"Sayo Device Backup File 1.0".ljust(64, b"\0")
BACKUP_RECORD_START = 0x69
BACKUP_RECORD = struct.Struct("<BBI")
BACKUP_LAYER_SIZE = 8
BACKUP_KEY_COMMAND = 0x10
BACKUP_LIGHT_COMMAND = 0x11
BACKUP_LIGHT_RGB_OFFSET = 20
BACKUP_LIGHT_MODE_OFFSET = 17
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


def packet(command, payload):
    prefix = bytes((REPORT_ID, command, len(payload))) + payload
    return (prefix + bytes((sum(prefix) & 0xff,))).ljust(REPORT_SIZE, b"\0")


class Device:
    def __init__(self, fd):
        self.fd = fd

    def exchange(self, command, payload, timeout=1):
        frame = packet(command, payload)
        if os.write(self.fd, frame) != len(frame):
            raise ValueError("HIDレポートを最後まで送信できませんでした。")
        deadline = time.monotonic() + timeout
        while select.select([self.fd], [], [], max(0, deadline - time.monotonic()))[0]:
            reply = os.read(self.fd, REPORT_SIZE)
            if not reply or reply[0] == REPORT_ID:
                break
            if time.monotonic() >= deadline:
                raise ValueError(f"コマンド 0x{command:02x} の応答がありません。")
        else:
            raise ValueError(f"コマンド 0x{command:02x} の応答がありません。")
        if len(reply) != REPORT_SIZE or reply[2] > 60:
            raise ValueError("応答のHIDレポート形式が一致しません。")
        if reply[1]:
            raise ValueError(f"コマンド 0x{command:02x} が拒否されました (0x{reply[1]:02x})。")
        return reply[3:3 + reply[2]]

    def read_key(self, index):
        payload = self.exchange(KEY_MAP, bytes((0, index)))
        extra = len(payload) - HEADER_SIZE
        if (extra not in range(LAYER_SIZE, (MAX_LAYERS + 1) * LAYER_SIZE, LAYER_SIZE)
                or payload[1] != index):
            raise ValueError(f"キー {index + 1} の応答形式が一致しません。")
        return payload

    def write_key(self, index, payload):
        self.exchange(KEY_MAP, bytes((1,)) + payload[1:])
        if self.read_key(index)[HEADER_SIZE:] != payload[HEADER_SIZE:]:
            raise ValueError("書き込み後の読み戻しが一致しません。")

    def save(self):
        self.exchange(4, bytes.fromhex("72 96"), timeout=2)


class Backup:
    def __init__(self, path):
        self.data = bytearray(path.read_bytes())
        end = len(self.data)
        if not self.data.startswith(BACKUP_MAGIC) or end < BACKUP_RECORD_START:
            raise ValueError("対応する Sayo Device Backup File 1.0 ではありません。")

        self.keys = {}
        self.lights = {}
        offset = BACKUP_RECORD_START
        while offset < end:
            if end - offset < BACKUP_RECORD.size:
                raise ValueError("バックアップのレコードヘッダーが途中で切れています。")
            command, index, size = BACKUP_RECORD.unpack_from(self.data, offset)
            payload = offset + BACKUP_RECORD.size
            offset = payload + size
            if offset > end:
                raise ValueError("バックアップのレコードが途中で切れています。")
            if command == BACKUP_KEY_COMMAND:
                if index in self.keys or size != HEADER_SIZE + MAX_LAYERS * BACKUP_LAYER_SIZE:
                    raise ValueError("バックアップのキー設定レコードが一致しません。")
                self.keys[index] = payload + HEADER_SIZE
            elif command == BACKUP_LIGHT_COMMAND:
                if index in self.lights or size != 56:
                    raise ValueError("バックアップの照明レコードが一致しません。")
                self.lights[index] = payload
        if self.keys.keys() != set(range(KEY_COUNT)):
            raise ValueError("バックアップに24キー分の設定がありません。")

    def read_key(self, index):
        # Convert to the CLI's legacy key layout. The backup stores three
        # additional bytes between the mode and the four parameters.
        start = self.keys[index]
        payload = bytearray(HEADER_SIZE)
        payload[1] = index
        for offset in range(start, start + MAX_LAYERS * BACKUP_LAYER_SIZE, BACKUP_LAYER_SIZE):
            payload.extend((self.data[offset], 0))
            payload.extend(self.data[offset + 4:offset + 8])
        return bytes(payload)

    def write_key(self, index, payload):
        for layer in range(1, MAX_LAYERS + 1):
            offset = self.keys[index] + (layer - 1) * BACKUP_LAYER_SIZE
            values = binding(payload, layer)
            self.data[offset] = values[0]
            self.data[offset + 4:offset + 8] = values[1:]

    def export(self, path):
        with tempfile.TemporaryDirectory(dir=path.parent) as directory:
            temporary = Path(directory) / "backup"
            temporary.write_bytes(self.data)
            os.link(temporary, path)

    def lighting(self, indices, layer, color=None, mode=None):
        if any(index not in self.lights for index in indices):
            raise ValueError("指定したキーの照明レコードがありません。")
        result = []
        for index in indices:
            payload = self.lights[index] + (layer - 1) * BACKUP_LAYER_SIZE
            rgb = payload + BACKUP_LIGHT_RGB_OFFSET
            mode_offset = payload + BACKUP_LIGHT_MODE_OFFSET
            if color is not None:
                self.data[rgb:rgb + 3] = color
            if mode is not None:
                self.data[mode_offset] = mode
            result.append({
                "key": index + 1,
                "color": "#" + self.data[rgb:rgb + 3].hex(),
                "mode": self.data[mode_offset],
            })
        return result


@contextmanager
def open_device(path):
    candidates = [
        node for node, _, name, desc in devices()
        if "boot" not in name.casefold() and b"\x06\x00\xff" in desc
        and b"\x85\x02" in desc and (path is None or path == node)
    ]
    if len(candidates) != 1:
        raise ValueError("対象の旧HID設定インターフェースを1つ選べません。list で確認してください。")
    fd = os.open(candidates[0], os.O_RDWR | os.O_NONBLOCK)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield Device(fd)
    finally:
        os.close(fd)


def layer_offset(payload, layer):
    offset = HEADER_SIZE + (layer - 1) * LAYER_SIZE
    if offset + LAYER_SIZE > len(payload):
        raise ValueError(f"指定したレイヤー {layer} はこのキーにありません。")
    return offset


def binding(payload, layer):
    offset = layer_offset(payload, layer)
    return payload[offset:offset + 1] + payload[offset + 2:offset + LAYER_SIZE]


def describe(payload):
    return {
        "key": payload[1] + 1,
        "layers": [
            list(binding(payload, layer))
            for layer in range(1, (len(payload) - HEADER_SIZE) // LAYER_SIZE + 1)
        ],
    }


def parse_binding(value):
    try:
        result = bytes(int(part, 16) for part in value.split(":"))
        if len(result) == 5:
            return result
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("5つの16進バイトを : で区切ってください。")


def parse_shortcut(value):
    *modifiers, key = value.upper().split("+")
    try:
        mask = sum(MODIFIERS[modifier] for modifier in set(modifiers))
        return bytes((0, mask, KEY_CODES[key], 0, 0))
    except KeyError as exc:
        raise argparse.ArgumentTypeError(f"未対応のキー名: {exc.args[0]}") from exc


def parse_color(value):
    if not re.fullmatch(r"#?[0-9a-fA-F]{6}", value):
        raise argparse.ArgumentTypeError("色を RRGGBB 形式で指定してください。")
    return bytes.fromhex(value.removeprefix("#"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--device", type=Path, help="対象の /dev/hidrawN")
    target.add_argument("--backup", type=Path, help="入力の .sayobak ファイル")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="SayoDeviceのHID一覧")
    commands.add_parser("read", help="24キー分の割り当てをJSONで表示")
    read_light = commands.add_parser("read-light", help="バックアップの24キー分のRGB照明を表示")
    light = commands.add_parser("set-light", help="バックアップのRGB照明を変更")
    light.add_argument("key", choices=[str(key) for key in range(1, KEY_COUNT + 1)] + ["all"],
                       metavar="KEY|all")
    light.add_argument("--color", type=parse_color, required=True, metavar="RRGGBB")
    light.add_argument("--mode", choices=("static", "held"), help="常時点灯または押下時点灯")
    for lighting_command in (read_light, light):
        lighting_command.add_argument("--layer", type=int, choices=range(1, MAX_LAYERS + 1),
                                      default=1, help="照明レイヤー (既定: 1)")
    light_destination = light.add_mutually_exclusive_group(required=True)
    light_destination.add_argument("--output", type=Path, help="新規 .sayobak ファイルの出力先")
    light_destination.add_argument("--dry-run", action="store_true", help="変更後の照明を表示")
    edit = commands.add_parser("set", help="1キーの1レイヤーを変更")
    edit.add_argument("key", type=int, choices=range(1, KEY_COUNT + 1), metavar="KEY")
    edit.add_argument("--layer", type=int, choices=range(1, MAX_LAYERS + 1), default=1)
    source = edit.add_mutually_exclusive_group(required=True)
    source.add_argument("--copy-from", type=int, choices=range(1, KEY_COUNT + 1), metavar="KEY")
    source.add_argument("--binding", type=parse_binding, metavar="MODE:P0:P1:P2:P3")
    source.add_argument("--shortcut", type=parse_shortcut, metavar="CTRL+SHIFT+F13")
    edit.add_argument("--dry-run", action="store_true", help="変更後の割り当てを表示")
    destination = edit.add_mutually_exclusive_group()
    destination.add_argument("--save", action="store_true", help="本体の不揮発メモリーに保存")
    destination.add_argument("--output", type=Path, help="新規 .sayobak ファイルの出力先")
    args = parser.parse_args(argv)
    if args.command == "list" and args.backup:
        parser.error("list に --backup は指定できません。")
    if args.command in ("read-light", "set-light") and not args.backup:
        parser.error("照明コマンドには --backup が必要です。")
    if args.command == "set":
        if args.dry_run and (args.save or args.output):
            parser.error("--dry-run と --save / --output は同時に指定できません。")
        if args.backup and (args.save or not (args.dry_run or args.output)):
            parser.error("--backup での set には --output または --dry-run を指定してください。")
        if args.output and not args.backup:
            parser.error("--output には --backup が必要です。")

    try:
        if args.command == "read-light":
            print(json.dumps(Backup(args.backup).lighting(range(KEY_COUNT), args.layer), indent=2))
            return 0
        if args.command == "set-light":
            backup = Backup(args.backup)
            indices = range(KEY_COUNT) if args.key == "all" else [int(args.key) - 1]
            mode = {"static": 0, "held": 1}.get(args.mode)
            result = backup.lighting(indices, args.layer, args.color, mode)
            if args.output:
                backup.export(args.output)
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "list":
            for node, pid, name, desc in devices():
                reports = [f"0x{rid:02x}" for rid in (2, 0x21) if bytes((0x85, rid)) in desc]
                print(f"{node} 8089:{pid:04x} {name} (report {', '.join(reports) or '-'})")
            return 0

        target = nullcontext(Backup(args.backup)) if args.backup else open_device(args.device)
        with target as device:
            keys = [device.read_key(index) for index in range(KEY_COUNT)]
            if args.command == "read":
                print(json.dumps([describe(key) for key in keys], indent=2))
                return 0

            index = args.key - 1
            current = keys[index]
            offset = layer_offset(current, args.layer)
            new_binding = args.binding or args.shortcut
            if args.copy_from is not None:
                new_binding = binding(keys[args.copy_from - 1], args.layer)
            updated = bytearray(current)
            updated[offset] = new_binding[0]
            updated[offset + 2:offset + LAYER_SIZE] = new_binding[1:]
            if not args.dry_run and updated != current:
                device.write_key(index, bytes(updated))
            if args.save:
                device.save()
            if args.output:
                device.export(args.output)
            print(json.dumps(describe(updated)))
        return 0
    except (OSError, ValueError) as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
