# SayoDevice 24キー設定ツール

[English](README.md)

24キーのSayoDevice向けPython 3 CLIです。USB接続または `.sayobak` 設定ファイルからキー割り当てを読み書きでき、設定ファイル内のRGB照明も設定できます。追加のPythonパッケージは不要です。 CLIのヘルプとエラーメッセージは英語で表示されます。

Osikiriという名前は、地名の「押切」と、キーを「押す」ことにちなんでいます。

## 設定を変換・転送するコマンド

| データの流れ | コマンド |
| --- | --- |
| 本体 → ファイル | `pull` |
| バイナリファイル → 本体 | `push` |
| テキスト → バイナリ | `encode` |
| バイナリ → テキスト | `decode` |

## コマンドのヘルプ

サブコマンドを先に書き、その後にオプションを指定します。`--help` でコマンド一覧を表示できます。各コマンドのオプションを確認するには、コマンド名の後に `--help` を付けます。

```sh
./osikiri --help
./osikiri set --help
./osikiri set-light --help
```

## USBで接続する

USB接続にはLinuxの `hidraw` と旧HID設定プロトコル（Report ID `0x02`、Usage Page `0xFF00`）を使います。対象の `/dev/hidrawN` への読み書き権限が必要です。

```sh
./osikiri list
./osikiri read --device /dev/hidrawN
```

`list` が表示したデバイスパスを指定します。旧設定インターフェースが1つなら `--device` を省略できます。`8089:0008` のLeftとRightは、それぞれのパスで選択します。再接続するとデバイス番号が変わることがあります。

`read` は本体のキー番号順に24キーを表示します。キー番号と物理位置の対応は機種やファームウェアに依存します。

### JSON出力の読み方（USB接続）

出力は、キーごとのオブジェクトを並べたJSON配列です。配列内の1件を例に示します。

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

`key` は本体のキー番号です。`layers` はFn 0から順に並ぶため、`layers[0]` がFn 0です。各要素には `[MODE, P0, P1, P2, P3]` が10進数で入ります。この例ではFn 0がCtrl+Shift+F13、Fn 1がYです。10進数の `104` と `28` は、`show` の表では16進数の `68` と `1C` に当たります。

## キー割り当てを変更する

```sh
# キーID 1のFn 0の割り当てをキーID 0へコピー
./osikiri set --device /dev/hidrawN 0 --copy-from 1 --layer 0

# キーID 6のショートカットをプレビュー
./osikiri set --device /dev/hidrawN 6 --shortcut Ctrl+Shift+F13 --dry-run

# ショートカットを適用して本体に保存
./osikiri set --device /dev/hidrawN 6 --shortcut Ctrl+Shift+F13 --save
```

`--shortcut` では英数字、F1〜F24、矢印キー、Enterなどの一般的なキーを指定できます。修飾キーにはCtrl、Shift、Alt、Gui（Windows / Command）を使います。右側の修飾キーには `RCtrl` のように `R` を付けます。

`read` は各レイヤーのモード1バイトとパラメーター4バイトを10進数で表示します。既知の割り当てを直接入力するには、`set 0 --binding MODE:P0:P1:P2:P3` に16進数のバイト値を指定します。値の意味はファームウェアに依存します。

ツールは編集前に全24キーを読み取ります。変更を書き込んだ場合は、対象キーの設定を読み戻して結果を確認してから `--save` を実行します。保存すると、本体の現在の設定が不揮発メモリーに記録されます。

## 互換性

`8089:0008` のLeftとRightの両方で、全24キー・5レイヤーの読み取りと、変更内容のプレビューを確認しました。書き込みと保存は模擬HIDで検証しました。Report ID `0x21` がある場合は `list` に表示されます。キー編集には旧設定インターフェース `0x02` が必要です。

- [sayodevice-controller（Report ID 0x21を使う6キーSayoDevice用RGBコントローラー）](https://github.com/kennedn/sayodevice-controller/blob/main/README.md)
- [Sayobot Sayo_CLIの旧HID実装](https://github.com/Sayobot/Sayo_CLI/blob/main/o2_protocol.cpp)

## キー割り当てと照明を確認する

```sh
./osikiri show --src original.sayobak
```

公式ツールと同じキーID 0〜23、Fnレイヤー0〜4を表で表示します。CLIの引数とJSONのキーIDも同じ番号を使います。旧バージョンの引数を使う場合は、キー番号とレイヤー番号から1を引いてください。各行にはキー番号、割り当て（モードと4個のパラメーターを16進数で表示）、RGB色、点灯トリガーの数値が含まれます。公式ツールの Light Mode には Static や Breathing などの点灯効果があります。このCLIはトリガー値を表示し、常時点灯と押下時点灯の設定に対応します。

### 物理キーの配置（Left）

公式ツールでUSBアイコンが右にある向きのLeftの配置です。数字は `show` と公式ツールで共通の `Key ID` です。

```text
 23   16   15    8    7    0
 22   17   14    9    6    1
 21   18   13   10    5    2     USB →
 20   19   12   11    4    3
```

右下は `Key ID 3`、その左隣は `Key ID 4` です。

### 物理キーの配置（Right）

USBコネクタが左にある向きのRightの配置です。数字は `show` と公式ツールで共通の `Key ID` です。

```text
         3    4   11   12   19   20
← USB    2    5   10   13   18   21
         1    6    9   14   17   22
         0    7    8   15   16   23
```

### Binding (hex) の読み方

Binding（バインディング）は、キーに割り当てられた動作です。`Binding (hex)` 列は、5つの値を `MODE:P0:P1:P2:P3` の順に16進数で表示します。

モードが `00`（通常のキー入力）の場合、`P0` は修飾キーのビットマスク、`P1` はUSB HIDキーコードです。`P2` と `P3` は使いません。

| Binding (hex) | 意味 |
| --- | --- |
| `00:03:68:00:00` | Ctrl+Shift+F13。マスク `03` はCtrl（`01`）とShift（`02`）の組み合わせで、`68` はF13です。 |
| `00:00:1C:00:00` | 修飾キーなしのY。マスクは `00` で、`1C` はYです。 |

ほかのモードでは、4つのパラメーターの意味がモードによって変わります。

### キー割り当てのMODE一覧

`MODE` はキー割り当ての先頭バイトです。表には公式ガイドに掲載されているモードを示します。利用できるモードは機種やファームウェアによって異なります。 [公式キー設定ガイド](https://github.com/Sayobot/SayoDevice_manual/blob/main/docs/en/docs/std/web_hid/key.md)

| モード | 値（10進 / 16進） | 動作 |
| --- | --- | --- |
| Default | `0` / `00` | キーと必要に応じて修飾キーを送信します。 |
| Keyboard | 未確認 | Defaultの追加遅延なしでキー入力を送信します。 |
| Two-Step Key | 未確認 | 押下と解放で別々のショートカットを実行します。 |
| Tap/Hold | 未確認 | 短押しと長押しで異なる動作を実行します。 |
| Mouse | 未確認 | クリック、カーソル移動、スクロールを行います。 |
| Media Controls | 未確認 | 音量や再生などを操作します。 |
| Keyboard + LED Control | 未確認 | ショートカットを送信し、キーボードのロック状態のインジケーターを制御します。 |
| A+B+C+D | 未確認 | 最大4キーを順に押し、まとめて解放します。 |
| One-key Password | 未確認 | 保存済みのASCII文字列を入力します。 |
| One-key Web | 未確認 | Windowsで設定したWebアドレスを開きます。 |
| One-key Text | 未確認 | 保存済みのテキストを入力します。 |
| Shortcut ×3 | 未確認 | 最大3つのショートカットを順に実行します。 |
| Loop Input | 未確認 | 押している間、キー入力を繰り返します。 |
| Lock Mode | 未確認 | 次に押すまでキーを押した状態にします。 |
| Gamepad Button | 未確認 | ゲームパッドのボタン入力を送信します。 |
| Key-to-Axis | 未確認 | キーをジョイスティックやマウスの軸に割り当てます。 |
| Num Lock Virtual Layer | 未確認 | Num Lockの状態に応じて動作を選びます。 |
| FN Layer Switching | 未確認 | 押している間だけレイヤーを切り替えます。 |
| SW Layer Switching (Set Fn Layer) | `128` / `80` | 押すとレイヤーが切り替わり、離してもそのレイヤーを維持します。 |
| Bluetooth Device Switching | 未確認 | Bluetooth接続先を切り替えます。 |

LeftのFn 0にある `Key ID 4` の割り当ては `80:02:00:00:00` で、Fn 2に切り替えます。

## .sayobak 設定ファイルを編集する

```sh
./osikiri set --src original.sayobak 6 --shortcut Ctrl+Shift+F13 --dest out
```

形式バージョン1.0の .sayobak サンプルで確認した24キー・5レイヤーの形式をオフラインで編集できます。出力ではRGB設定を含め、編集したキー割り当て以外のバイトがすべて保持されます。`--dest` で出力先ディレクトリを指定できます。`--copy-from`、`--binding`、`--dry-run` も同様に使えます。公式ツールでの編集済みファイルの取り込みは未確認です。

## 設定ファイルのRGB照明を設定する

```sh
./osikiri read-light --src original.sayobak --layer 1
./osikiri set-light --src original.sayobak 6 --layer 1 --color FF6600 --mode static --dry-run
./osikiri set-light --src original.sayobak 6 --layer 1 --color FF6600 --mode static --dest out
```

キーIDは0〜23で、全キーをまとめて変更するには `all` を指定します。色は6桁の16進RGBで指定します。`--mode static` は常時点灯、`--mode held` は押している間の点灯です。`--mode` を省略すると現在のモードを維持します。照明コマンドは設定ファイルをオフラインで編集します。編集済みファイルの復元と実機での点灯は未確認です。

どちらのコマンドでも `--layer 0` から `--layer 4` で設定ファイルの照明スロットを指定できます。省略時はFn 0です。Fn 1〜4の実機での動作は未確認です。

### Light Modeと点灯トリガーの値

公式ツールの **Light Mode** は点灯効果を選ぶ項目です。下表に各効果と、確認できたファイル上の番号を示します。採取されたStaticのレポートでは効果の番号は `0` です。ほかの効果の番号は未確認です。 [公式の照明設定ガイド](https://github.com/Sayobot/SayoDevice_manual/blob/main/docs/en/docs/std/web_hid/led.md) · [採取されたStaticのレポート](https://github.com/kennedn/sayodevice-controller/blob/main/README.md#protocol)

| Light Mode | ファイル上の番号 | 効果 |
| --- | --- | --- |
| Static | `0` | 明るさが一定で、点灯はトリガーに従う |
| Indicator | 未確認 | Num Lock、Caps Lock、Scroll Lockの状態を表示する |
| Breathing | 未確認 | 明るくなったり暗くなったりを繰り返す |
| Breathing Once | 未確認 | トリガーで明暗の変化を1周期実行する |
| Wave | 未確認 | 固定色以外のカラーモードで色を動かす |
| Switch | 未確認 | 設定した間隔で色を順番に切り替える |
| Switch Once | 未確認 | トリガーで次の色に切り替える |
| Blink | 未確認 | 設定した点灯・消灯間隔で点滅する |
| Blink Once | 未確認 | トリガーで点滅する |
| Fade out | 未確認 | トリガーで徐々に消灯する |
| Fade in | 未確認 | トリガーで徐々に点灯する |

`show` の **Light trigger** 列は点灯トリガーの値を表示します。`read-light` は同じ値をJSONの `mode` に出力します。CLIの `set-light --mode` が変更するのもこのトリガーです。

| トリガー値 | CLIオプション | Staticでの点灯条件 |
| --- | --- | --- |
| `0` | `--mode static` | 常時点灯 |
| `1` | `--mode held` | キーを押している間だけ点灯 |

## 本体と設定ファイルを同期する

```sh
./osikiri pull
./osikiri pull /dev/hidrawN
./osikiri pull --device /dev/hidrawN --dest out
./osikiri push --device /dev/hidrawN --src out/SayoDevice-Left-2026-11-23-12-00-00.sayobak --dry-run
./osikiri push --device /dev/hidrawN --src out/SayoDevice-Left-2026-11-23-12-00-00.sayobak --apply --save
```

`pull` は、HID Report ID `0x21` で全24キー・5つのFnレイヤーのキー割り当てとRGB照明を読み取ります。入力は本体だけです。 本体のパスを省略すると、接続中の対応機器をすべて読み取ります。HIDのパスを直接指定するか `--device` で指定すると、その1台だけを読み取ります。ファイルを出力する前に本体名とパスを表示します。 本体から別のHIDレポートが届いた場合は、要求したレコードと一致する応答を待ちます。生成する `.sayobak` には、Osikiriが読み取ったキー割り当てと照明のレコードだけが入ります。スクリプトやカラーテーブルは出力対象外です。このファイルの公式ツールでの取り込みは未確認です。`push` はバイナリファイルのキー割り当てと照明だけを適用し、変更したレコードを読み戻して確認します。`--save` を指定すると、成功した変更を本体の不揮発メモリーに保存します。途中で書き込みに失敗した場合、すでに書き込んだレコードが本体の動作中の設定に反映されることがあります。

バイナリの `.sayobak` を書き出すコマンドは、編集可能なJSONを入れた同名の `.json` も出力します。ファイル名はローカル時刻の24時間制で `yyyy-MM-dd-hh-mm-ss.json` と `yyyy-MM-dd-hh-mm-ss.sayobak` になります。ペアには同じ日時を使います。 `pull` では、空白やファイル名の区切り文字をハイフンに置き換えた本体名を日時の前に付けます。例は `SayoDevice-Left-2026-11-23-12-00-00.sayobak` です。同名ファイルがある場合は、空いている名前が見つかるまで日時を1秒ずつ進めます。`--dest` は出力先ディレクトリを指定し、省略時は `out/` です。必要に応じてディレクトリを作成し、生成したパスを表示します。後続のコマンドではそのパスを使ってください。

## テキストとバイナリを相互変換する

```sh
./osikiri decode original.sayobak --dest out
./osikiri encode --src out/2026-11-23-12-00-00.json --dest out
```

`decode` の入力ファイルは直接指定するか、`--src` で指定できます。

`keys[].id` が、そのキーの全レイヤーに共通するIDです。`lighting` オブジェクトには `color` と `mode` が入ります。`keys[].layers[].binding` は `MODE:P0:P1:P2:P3` の16進形式で編集できます。RGBと点灯トリガーは `lighting.color` と `lighting.mode` で指定します。

`encode` では、JSONの `binding`、`lighting.color`、`lighting.mode` が、`source_binary` 内の対応する値より優先されます。たとえば、埋め込みのバイナリでYが割り当てられていても、JSONで `00:03:68:00:00` を指定すると、出力ではCtrl+Shift+F13になります。

埋め込みの `source_binary` はスクリプトやカラーテーブルなど、これらの項目以外の元データを保持するので、そのまま残してください。テキストを変更せずに変換すると、元とバイト単位で同じバイナリになります。
