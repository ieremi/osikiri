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
./osikiri pull --help
./osikiri encode --help
```

## USBで接続する

Linuxの `hidraw` を使います。対象の `/dev/hidrawN` への読み書き権限が必要です。`pull` は読み取った本体の名前とHIDパスを表示します。LeftとRightの両方を接続している場合は、`push --device` で書き込み先を指定します。再接続でパスが変わることがあります。

## 互換性

`8089:0008` のLeftとRightの両方で、全24キー・5レイヤーの読み取りと、変更内容のプレビューを確認しました。書き込みと保存は模擬HIDで検証しました。同期にはReport ID `0x21` を使います。現在の `push` は旧設定インターフェース `0x02` を選択します。

- [sayodevice-controller（Report ID 0x21を使う6キーSayoDevice用RGBコントローラー）](https://github.com/kennedn/sayodevice-controller/blob/main/README.md)
- [Sayobot Sayo_CLIの旧HID実装](https://github.com/Sayobot/Sayo_CLI/blob/main/o2_protocol.cpp)

## キー割り当てと照明を確認する

`pull` または `decode` が生成したJSONを開きます。キーID 0〜23とFnレイヤー0〜4は公式ツールの番号と同じです。`binding` にキー割り当て、`lighting` にRGB色、点灯トリガー、点灯効果の番号が入ります。

### 物理キーの配置（Left）

公式ツールでUSBアイコンが右にある向きのLeftの配置です。数字はJSONの `keys[].id` と公式ツールで共通のキーIDです。

```text
 23   16   15    8    7    0
 22   17   14    9    6    1
 21   18   13   10    5    2     USB →
 20   19   12   11    4    3
```

右下は `Key ID 3`、その左隣は `Key ID 4` です。

### 物理キーの配置（Right）

USBコネクタが左にある向きのRightの配置です。数字はJSONの `keys[].id` と公式ツールで共通のキーIDです。

```text
         3    4   11   12   19   20
← USB    2    5   10   13   18   21
         1    6    9   14   17   22
         0    7    8   15   16   23
```

### binding の読み方

Binding（バインディング）は、キーに割り当てられた動作です。JSONの `binding`は、5つの値を `MODE:P0:P1:P2:P3` の順に16進数で表示します。

モードが `00`（通常のキー入力）の場合、`P0` は修飾キーのビットマスク、`P1` はUSB HIDキーコードです。`P2` と `P3` は使いません。

| binding | 意味 |
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

### Light Modeと点灯トリガーの値

公式ツールの **Light Mode** は点灯効果を選ぶ項目です。下表に各効果と、確認できたファイル上の番号を示します。Staticの効果番号は `0` です。公式ツールでは効果番号 `1` がIndicator、`2` がBreathingと表示されました。残りの番号は未確認です。 [公式の照明設定ガイド](https://github.com/Sayobot/SayoDevice_manual/blob/main/docs/en/docs/std/web_hid/led.md) · [採取されたStaticのレポート](https://github.com/kennedn/sayodevice-controller/blob/main/README.md#protocol)

| Light Mode | ファイル上の番号 | 効果 |
| --- | --- | --- |
| Static | `0` | 明るさが一定で、点灯はトリガーに従う |
| Indicator | `1` | Num Lock、Caps Lock、Scroll Lockの状態を表示する |
| Breathing | `2` | 明るくなったり暗くなったりを繰り返す |
| Breathing Once | 未確認 | トリガーで明暗の変化を1周期実行する |
| Wave | 未確認 | 固定色以外のカラーモードで色を動かす |
| Switch | 未確認 | 設定した間隔で色を順番に切り替える |
| Switch Once | 未確認 | トリガーで次の色に切り替える |
| Blink | 未確認 | 設定した点灯・消灯間隔で点滅する |
| Blink Once | 未確認 | トリガーで点滅する |
| Fade out | 未確認 | トリガーで徐々に消灯する |
| Fade in | 未確認 | トリガーで徐々に点灯する |

JSONの `lighting.trigger` は点灯トリガーです。Light Modeの番号は `lighting.effect` に指定します。たとえばStaticは `0`、Indicatorは `1`、Breathingは `2` です。RGB色は `lighting.color` に `"#00BFFF"` のように指定します。

| トリガー値 | Staticでの点灯条件 |
| --- | --- |
| `0` | 常時点灯 |
| `1` | キーを押している間だけ点灯 |
| `2` | キーを離すと点灯（公式ツールでは **Release Light Up**） |

Indicator（`effect: 1`）では、公式ツールに **Indicator** の選択欄が表示されます。この効果で確認済みの値は、`trigger: 1` が **NumLock**、`trigger: 2` が **CapsLock**、`trigger: 4` が **ScrollLock** です。

選択欄には **ComposeLock** と **KanaLock** も表示されます。対応する `trigger` 値は未確認です。

Breathingを4xで使う場合の `lighting` の例です。

```json
{
  "effect": 2,
  "color": "#0000ff",
  "speed": 4,
  "light_duration": 37,
  "dark_duration": 149,
  "trigger": 2
}
```

確認済みの速度は4xと8xで、`speed` に `4` または `8` を指定します。未確認の速度コードは `null` と表示され、エンコード時に元の速度を保持します。`light_duration` と `dark_duration` には、公式ツールと同じく `0`〜`255` の整数を指定します。

## 本体と設定ファイルを同期する

```sh
./osikiri pull
./osikiri pull /dev/hidrawN
./osikiri pull --device /dev/hidrawN --dest out
./osikiri push --device /dev/hidrawN --src out/SayoDevice-Left-2026-11-23-12-00-00.sayobak --dry-run
./osikiri push --device /dev/hidrawN --src out/SayoDevice-Left-2026-11-23-12-00-00.sayobak
```

`pull` は、対応する `8089:0008` の本体オプションと、全24キー・5つのFnレイヤーのキー割り当てとRGB照明をHID Report ID `0x21` で読み取ります。パスを省略すると対応機器をすべて読み取り、直接指定するか `--device` で指定すると1台を読み取ります。

`push` はバイナリファイルのキー割り当てと照明だけを適用し、変更したレコードを読み戻して確認し、本体の不揮発メモリーに保存します。動作中の設定とファイルが一致している場合も保存します。差分だけを確認するには `--dry-run` を使います。書き込みや保存は行われません。途中で書き込みに失敗した場合、すでに書き込んだレコードが本体の動作中の設定に反映されることがあります。

バイナリの `.sayobak` を書き出すコマンドは、編集可能なJSONを入れた同名の `.json` も出力します。ファイル名はローカル時刻の24時間制で `yyyy-MM-dd-hh-mm-ss.json` と `yyyy-MM-dd-hh-mm-ss.sayobak` になります。ペアには同じ日時を使います。 `pull` では、空白やファイル名の区切り文字をハイフンに置き換えた本体名を日時の前に付けます。例は `SayoDevice-Left-2026-11-23-12-00-00.sayobak` です。同名ファイルがある場合は、空いている名前が見つかるまで日時を1秒ずつ進めます。`--dest` は出力先ディレクトリを指定し、省略時は `out/` です。必要に応じてディレクトリを作成し、生成したパスを表示します。後続のコマンドではそのパスを使ってください。

## テキストとバイナリを相互変換する

```sh
./osikiri decode original.sayobak --dest out
./osikiri encode out/2026-11-23-12-00-00.json --dest out
```

`encode` と `decode` の入力ファイルは直接指定するか、`--src` で指定できます。

`keys[].id` が、そのキーの全レイヤーに共通するIDです。JSONは `lighting` の必須項目を `effect`、`color`、`speed`、`light_duration`、`dark_duration`、`trigger` の順で出力します。`keys[].layers[].binding` は `MODE:P0:P1:P2:P3` の16進形式で編集できます。バイナリから現在の形式のJSONを生成するには `decode` を使います。

`encode` では、JSONの `binding` と `lighting` の編集項目が、`source_binary` 内の対応する値より優先されます。たとえば、埋め込みのバイナリでYが割り当てられていても、JSONで `00:03:68:00:00` を指定すると、出力ではCtrl+Shift+F13になります。

### 公式形式のファイルを書き出す

`pull` は外部のひな型なしで、公式ファイルと同じ形式の識別子、本体オプション、キー割り当て、照明レコードを組み立てます。スクリプトやカラーテーブルなどの追加レコードは取り込みません。既存の公式ファイルに含まれる追加レコードを保持するには、そのファイルを `decode` してから編集し、`encode` します。

`encode` は `source_binary` の構造を引き継ぎます。機種識別子や本体オプションがない旧形式のJSONの場合は、再度 `pull` するか、公式ファイルを `decode` してください。生成したヘッダーとレコード構造は公式ファイルと照合済みです。Leftから `pull` で生成したファイルを、公式ツールで読み込めることを確認しました。

### `source_binary` の長さが違う理由

`source_binary` は元のバイナリ全体をBase64で保持します。JSONを編集するときはそのまま残してください。スクリプトやカラーテーブルが元データに含まれていれば、編集項目以外のバイトも含めて保持されます。JSONを変更せずに変換すると、元とバイト単位で同じバイナリになります。

| JSONの作成方法 | `source_binary` に含まれるデータ | サイズの例（バイナリ → Base64） |
| --- | --- | --- |
| `pull` | 本体オプション、キー割り当て、RGB照明 | 3,081バイト → 4,108文字 |
| 公式の `.sayobak` を `decode` | 追加データやパディングを含む入力ファイル全体 | 281,965バイト → 375,956文字 |

Base64にすると元のバイト数より約3分の1増え、パディングもそのまま残ります。`decode` の出力サイズは入力ファイルによって異なります。
