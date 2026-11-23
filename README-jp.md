# SayoDevice 24キー設定ツール

[English](README.md)

24キーのSayoDevice向けPython 3 CLIです。USB接続または `.sayobak` 設定ファイルからキー割り当てを読み書きでき、設定ファイル内のRGB照明も設定できます。追加のPythonパッケージは不要です。 CLIのヘルプとエラーメッセージは英語で表示されます。

## USBで接続する

USB接続にはLinuxの `hidraw` と旧HID設定プロトコル（Report ID `0x02`、Usage Page `0xFF00`）を使います。対象の `/dev/hidrawN` への読み書き権限が必要です。

```sh
python3 sayo24.py list
python3 sayo24.py --device /dev/hidrawN read
```

`list` が表示したデバイスパスを指定します。旧設定インターフェースが1つなら `--device` を省略できます。`8089:0008` のLeftとRightは、それぞれのパスで選択します。再接続するとデバイス番号が変わることがあります。

`read` は本体のキー番号順に24キーを表示します。キー番号と物理位置の対応は機種やファームウェアに依存します。

## キー割り当てを変更する

```sh
# キー2のレイヤー1の割り当てをキー1へコピー
python3 sayo24.py --device /dev/hidrawN set 1 --copy-from 2 --layer 1

# キー7のショートカットをプレビュー
python3 sayo24.py --device /dev/hidrawN set 7 --shortcut Ctrl+Shift+F13 --dry-run

# ショートカットを適用して本体に保存
python3 sayo24.py --device /dev/hidrawN set 7 --shortcut Ctrl+Shift+F13 --save
```

`--shortcut` では英数字、F1〜F24、矢印キー、Enterなどの一般的なキーを指定できます。修飾キーにはCtrl、Shift、Alt、Gui（Windows / Command）を使います。右側の修飾キーには `RCtrl` のように `R` を付けます。

`read` は各レイヤーのモード1バイトとパラメーター4バイトを10進数で表示します。既知の割り当てを直接入力するには、`set 1 --binding MODE:P0:P1:P2:P3` に16進数のバイト値を指定します。値の意味はファームウェアに依存します。

ツールは編集前に全24キーを読み取ります。変更を書き込んだ場合は、対象キーの設定を読み戻して結果を確認してから `--save` を実行します。保存すると、本体の現在の設定が不揮発メモリーに記録されます。

## 互換性

`8089:0008` のLeftとRightの両方で、全24キー・5レイヤーの読み取りと、変更内容のプレビューを確認しました。書き込みと保存は模擬HIDで検証しました。Report ID `0x21` がある場合は `list` に表示されます。キー編集には旧設定インターフェース `0x02` が必要です。

- [sayodevice-controller（Report ID 0x21を使う6キーSayoDevice用RGBコントローラー）](https://github.com/kennedn/sayodevice-controller/blob/main/README.md)
- [Sayobot Sayo_CLIの旧HID実装](https://github.com/Sayobot/Sayo_CLI/blob/main/o2_protocol.cpp)

## .sayobak 設定ファイルを編集する

```sh
python3 sayo24.py --src original.sayobak read
python3 sayo24.py --src original.sayobak set 7 --shortcut Ctrl+Shift+F13 --dest edited.sayobak
```

形式バージョン1.0の .sayobak サンプルで確認した24キー・5レイヤーの形式をオフラインで編集できます。出力ではRGB設定を含め、編集したキー割り当て以外のバイトがすべて保持されます。出力先には新規ファイルのパスを指定してください。`--copy-from`、`--binding`、`--dry-run` も同様に使えます。公式ツールでの編集済みファイルの取り込みは未確認です。

## 設定ファイルのRGB照明を設定する

```sh
python3 sayo24.py --src original.sayobak read-light --layer 2
python3 sayo24.py --src original.sayobak set-light 7 --layer 2 --color FF6600 --mode static --dry-run
python3 sayo24.py --src original.sayobak set-light 7 --layer 2 --color FF6600 --mode static --dest edited.sayobak
```

キー番号は1〜24で、全キーをまとめて変更するには `all` を指定します。色は6桁の16進RGBで指定します。`--mode static` は常時点灯、`--mode held` は押している間の点灯です。`--mode` を省略すると現在のモードを維持します。照明コマンドは設定ファイルをオフラインで編集します。編集済みファイルの復元と実機での点灯は未確認です。

どちらのコマンドでも `--layer 1` から `--layer 5` で設定ファイルの照明スロットを指定できます。省略時はレイヤー1です。レイヤー2〜5の実機での動作は未確認です。
