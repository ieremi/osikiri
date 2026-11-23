# SayoDevice 24キー設定ツール

[English](README.md)

Linux の `hidraw` を使い、旧 HID 設定プロトコル（Report ID `0x02`、Usage Page `0xFF00`）を話す SayoDevice のキー割り当てを読み書きする Python 3 CLI です。USB 接続と対象の `/dev/hidrawN` への読み書き権限が必要です。Python の追加パッケージは不要です。

```sh
python3 sayo24.py list
python3 sayo24.py --device /dev/hidrawN read
```

`hidrawN` は一覧に表示されたパスに置き換えます。旧設定インターフェースが1つなら `--device` は省略できます。`read` は本体のキー番号順に24キーを表示します。物理配置と番号の対応は機種やファームウェアに依存します。

```sh
# キー2のレイヤー1の割り当てをキー1へコピー
python3 sayo24.py set 1 --copy-from 2 --layer 1

# 同じ設定を本体の不揮発メモリーに保存
python3 sayo24.py set 1 --copy-from 2 --layer 1 --save
```

`read` の各レイヤーはモードと4個のパラメーターを10進数で表示します。既知の割り当てを直接入力する場合、`set 1 --binding MODE:P0:P1:P2:P3` に16進のバイト値を指定します。値の意味はファームウェアに依存します。変更時は全24キーを読み取った後、指定したキーとレイヤーを編集し、読み戻しが一致した場合にのみ `--save` を実行します。保存コマンドは本体全体の現在の設定を保存します。

`8089:0008` の Left / Right 両方で各24キー・5レイヤーの読み取りを確認し、実機で変更プレビューも確認しました。書き込みと保存は模擬HIDで検証しました。設定インターフェースが Report ID `0x21` のみの場合は一覧で識別できます。キー編集には `0x02` の設定インターフェースが必要です。

- [参照の sayodevice-controller（6キー機のRGB、Report ID 0x21）](https://github.com/kennedn/sayodevice-controller/blob/main/README.md)
- [旧HID通信の実装元 Sayobot/Sayo_CLI](https://github.com/Sayobot/Sayo_CLI/blob/main/o2_protocol.cpp)

一般的なキー名で指定する場合は `--shortcut` を使います。英数字、F1–F24、矢印キー、Enter などに対応します。修飾キーは Ctrl、Shift、Alt、Gui（Windows / Command キー）です。右側の修飾キーは RCtrl などの名前で指定できます。

```sh
# 変更内容をプレビュー
python3 sayo24.py --device /dev/hidraw0 set 7 --shortcut Ctrl+Shift+F13 --dry-run

# 本体に適用して保存
python3 sayo24.py --device /dev/hidraw0 set 7 --shortcut Ctrl+Shift+F13 --save
```

この環境で認識された `8089:0008` の Left / Right は、それぞれ個別に指定します。番号は接続のたびに変わる可能性があります。
