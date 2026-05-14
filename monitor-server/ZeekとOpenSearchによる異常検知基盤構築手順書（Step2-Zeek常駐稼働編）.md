# Zeek と OpenSearch による 異常検知基盤構築手順書(Step2:Zeek常駐稼働編)

本書では、Ubuntu 24.04 Server に対してネットワーク監視フレームワーク Zeek をインストールおよび設定し、EtherNet/IP、Modbus、BACnetの通信を取得する手順をまとめた。

## 1. VirtualBoxおよびUbuntu 24.04 Serverの事前準備

### 1.1 ソフトウェアのダウンロード
1. **VirtualBoxのダウンロード・インストール**
   - [VirtualBox公式サイト](https://www.virtualbox.org/)からWindowsホスト用のインストーラーをダウンロードし、インストールする。
2. **Ubuntu 24.04 LTS ServerのISOイメージを取得**
   - [Ubuntu公式ダウンロードページ](https://ubuntu.com/download/server)から `Ubuntu 24.04.x LTS Server` のISOイメージ（.isoファイル）をダウンロードする。

### 1.2 Ubuntu 24.04 Serverの読み込み（インポート）
1. VirtualBoxを起動し、「新規」をクリックする。
2. 名前（`MonitorServer Ubuntu 24.04 Server`）、ISOイメージ（先ほどダウンロードしたUbuntuのISOを選択）を設定し、「自動インストールをスキップ（※推奨）」にチェックを入れて「次へ」進む。
3. **ハードウェア**:
   - メモリ(RAM): **4096 MB** (4GB) 以上を推奨
   - プロセッサ: **2 CPU** 以上を推奨
4. **ハードディスク**:
   - 仮想ハードディスクを作成: **40 GB** 以上を割り当てて「次へ」→「完了」。

### 1.3 Ubuntu 24.04 Serverのアダプタ設定（GUIでの実施）
VirtualBox GUIからアダプタを割り当てる。
(本例は、intnet7.1に接続の場合。各環境に合わせて変更すること)

1. VirtualBoxのメイン画面で対象のVM（`MonitorServer Ubuntu 24.04 Server`）を選択し、「設定」>「ネットワーク」を開く。
2. **「アダプター 1」**タブを開き、「ネットワークアダプターを有効化」にチェックを入れる。
   - **割り当て:** `内部ネットワーク`
   - **名前:** `intnet7.1`
3. **「アダプター 2」**のタブを開き、「ネットワークアダプターを有効化」にチェックを入れる。
   - **割り当て:** `NAT`
   - ポートフォワーディング
     名前:SSH, プロトコル:TCP, ホストポート:7132, ゲストポート:22
   ※ポートフォワーディングは、インターネット接続とホストOSとのSSHに用いる。開発時のみ有効とする。
4. 「OK」を押して保存する。

### 1.4 内部ネットワーク(intnet7.1)へのDHCPサーバーの割り当て
内部ネットワーク（`intnet7.1`,`intnet7.2`,`intnet7.3`）へのDHCPサーバーの設定は、各環境で実施する。

<参考>`intnet7.1`の場合、`10.7.1.128` から（`10.7.1.191` まで）のアドレスをDHCPで割り当てる。10.7.1.3から10.7.1.127を静的IPアドレス割り当てレンジとする。以下コマンドが各環境項目時に実行済みのはずである。

```powershell
.\VBoxManage dhcpserver add --netname intnet7.1 --ip 10.7.1.2 --netmask 255.255.255.0 --lowerip 10.7.1.128 --upperip 10.7.1.191 --enable
```

### 1.5 Ubuntu 24.04 Serverのインストール
1. 仮想マシンを「起動」する。
2. 言語選択で `English` を選択する。（Server版は日本語ではなく英語でのインストール・運用を強く推奨）
3. 画面の指示に従い、キーボード配列(Japanese)などを設定して進める。
4. **ネットワーク設定**: デフォルトのまま `Done` を選択。
5. **ストレージ構成**: デフォルトのまま `Done` を選択。
6. **プロファイル設定**: ユーザー名（例: `kali`）、パスワード等を設定する。
7. **SSH Setup**: **「Install OpenSSH server」にスペースキーで必ずチェックマーク（[X]）を入れる。**
8. **Featured Server Snaps**: 今回はDockerを公式リポジトリから最新版で入れるため、ここでは何もチェックせずに `Done` を選択。
9. インストールが完了したら `Reboot Now` を選択する。（※”Please remove the installation medium”と出たらEnterキーを押して再起動）

### 1.6 SSHサーバーの自動起動設定
OS起動時に自動で立ち上がるように設定する。これにより、次回以降のVM起動時には自動的にSSHが有効になる。

```bash
# 自動起動を有効化
sudo systemctl enable ssh
# サービスを起動
sudo systemctl start ssh
# 状態の確認
sudo systemctl status ssh
```

### 1.7 MonitorServerの静的IPアドレスの設定
MonitorServerの静的IPアドレスは、各プロトコル環境ごとに設定する。
4.1, 6.1, 7.1を参照。

### 1.8 タイムゾーン設定（Asia/Tokyo）
ログのタイムスタンプを日本時間（JST）に合わせるため、タイムゾーンを `Asia/Tokyo` に設定する。

```bash
sudo timedatectl set-timezone Asia/Tokyo
```

---
## 2. Zeekのインストール

Zeekは、openSUSE Build Service 経由で提供される公式パッケージを利用する。

### 2.1 リポジトリのGPGキー追加
```bash
curl -fsSL https://download.opensuse.org/repositories/security:zeek/xUbuntu_24.04/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/security_zeek.gpg > /dev/null
```

### 2.2 リポジトリの追加
```bash
echo 'deb http://download.opensuse.org/repositories/security:/zeek/xUbuntu_24.04/ /' | sudo tee /etc/apt/sources.list.d/security:zeek.list
```

### 2.3 インストールの実行
```bash
sudo apt update
sudo apt install zeek
```
> **注意**: インストール中に Postfix (メール設定) のプロンプトが表示される場合がある。監視専用のセンサーとして利用する場合は、「No configuration（設定なし）」または「Local only（ローカルのみ）」を選択して進める。

## 3. 基本的な起動確認とプラグインの準備

### 3.1 インターフェースの確認
監視するインターフェース（例: `eth0`, `enp0s3`など）を確認する。

```bash
ip addr show
```

### 3.2 zeekctlを用いた初期設定と起動
常駐稼働（デーモン化）を行うため、zeekctlを利用してZeekを起動・管理する。

**【手順1】監視インターフェースの設定**
`/opt/zeek/etc/node.cfg` を編集し、監視するインターフェース（例: `enp0s3`）を指定する。
```bash
sudo nano /opt/zeek/etc/node.cfg
```
以下のように `[zeek]` セクションの `interface` を変更する。
```ini
[zeek]
type=standalone
host=localhost
interface=enp0s3   # 実際のインターフェース名に変更
```

**【手順2】チェックサム検証の無効化（VM環境向け重要設定）**
> **注意**: VirtualBox等の仮想マシン環境ではTCP/UDP/IPのチェックサムがハードウェアオフロードにより正しく計算されないため、Zeekがパケットを破棄してしまう。手動起動時の `-C` オプションの代わりとして、恒久的にチェックサム検証を無視するよう設定する。

`/opt/zeek/share/zeek/site/local.zeek` を開き、末尾に以下を追記する。
```bash
echo 'redef ignore_checksums = T;' | sudo tee -a /opt/zeek/share/zeek/site/local.zeek
```

**【手順3】zeekctlによる設定適用と起動**
zeekctlコマンドを実行し、設定を反映してZeekをバックグラウンドで起動する。
```bash
sudo /opt/zeek/bin/zeekctl deploy
sudo /opt/zeek/bin/zeekctl status
```
statusが `running` になっていれば正常稼働している。

### 3.3 必要な開発モジュール（ライブラリ）のインストール
ENIP等の制御システム向け通信プロトコルは、Zeekの標準インストールに加えて専用のプラグインを導入することで、詳細な解析やログの出力が可能になる。
Zeek用プラグインのコンパイルに必要な C/C++ コンパイラや、Zeekの開発用ヘッダーファイルをインストールする。

```bash
sudo apt update
sudo apt install cmake make gcc g++ zeek-core-dev zeek-spicy-dev
```

### 3.4 Zeekパッケージの意図せぬアップデート防止（バージョン固定）
Zeekは公式リポジトリからaptでインストールしているため、後日OS全体に `apt upgrade` を実行した際、意図せずZeek本体だけが最新版にアップデートされてしまうことがある。
Zeek本体のみがアップデートされると、独自コンパイルしたプラグイン（C++バイナリ）とバージョン不整合（ABIミスマッチ）が生じ、パケット解析が完全に停止する致命的なエラーとなる。
これを防ぐため、以下のコマンドを実行してZeek関連のパッケージをアップデート対象から除外（ロック）しておく。

```bash
sudo apt-mark hold zeek zeek-core zeek-core-dev zeek-spicy-dev
```
※解除したい場合のみ `sudo apt-mark unhold <パッケージ名>` を実行する。

### 3.5 ZKG（Zeek Package Manager）の初期設定
初めてパッケージマネージャーを利用する場合は、設定ファイルを自動生成する。

```bash
sudo /opt/zeek/bin/zkg autoconfig
```

---

## 4. EtherNet/IPのログ取得手順

EtherNet/IP（ENIP/CIP）通信を監視する場合、専用のプラグインを導入して詳細な解析を行う。

### 4.1 MonitorServerのIPアドレスの設定（ENIP環境用）
MonitorServerのIPをENIP環境（10.7.1.0/24）に適応させる。`/etc/netplan/99-netcfg.yaml` を以下の通り変更する。

```yaml
    enp0s3:
      dhcp4: false
      addresses:
        - 10.7.1.32/24
```
その後、変更を適用する。

```bash
sudo netplan apply
```

### 4.2 EtherNet/IP解析プラグインのインストール
CISA提供のENIPプラグインをインストールする。

```bash
sudo /opt/zeek/bin/zkg install https://github.com/cisagov/icsnpp-enip
```
- testでエラーが発生しインストールを強制する場合は `--skiptests` オプションを使用する。

### 4.3 EtherNet/IP動作確認手順

**【手順1】プラグインの適用（zeekctl deploy）**
ZKGでインストールしたプラグインを稼働中のZeekに反映させるため、zeekctlでデプロイを実行する。（ZKGでインストールされたパッケージは自動的に読み込み対象となる）

```bash
sudo /opt/zeek/bin/zeekctl deploy
```

**【手順2】Zeekログの出力確認（ZeekゲストOS）**
ENIP通信発生後、zeekctlのデフォルトログ出力先である `/opt/zeek/logs/current/` 内に以下のログが新しく生成されていることを確認する。
- `enip.log`
- `enip_list_identity.log` （List Identity通信が行われた場合）
- `cip.log` （ENIP上でCIP通信が含まれている場合）

これらのファイルが存在し、内容が記録されていればEtherNet/IP通信が正しく認識できている状態である。

---
## 5. OPC UAのログ取得手順

ZeekでOPC UA（通常 TCP/UDP ポート 4840）のトラフィックを解析・ログ化するには、CISA提供の専用プラグインを導入する。

### 5.1 OPC UAプラグインのインストール
CISA提供のOPC UAバイナリ解析プラグインをインストールする。

```bash
sudo /opt/zeek/bin/zkg install icsnpp-opcua-binary
```

### 5.2 OPC UA動作確認手順

**【手順1】プラグインの適用（zeekctl deploy）**
インストールしたプラグインを稼働中のZeekに反映させる。

```bash
sudo /opt/zeek/bin/zeekctl deploy
```

**【手順2】Zeekログの出力確認（ZeekゲストOS）**
OPC UA通信発生後、`/opt/zeek/logs/current/`（稼働中の実体は `/opt/zeek/spool/zeek/`）内に以下のログが生成されていることを確認する。
- `opcua_binary.log`
- `opcua_binary_read.log`
- `opcua_binary_read_nodes_to_read.log`
- `opcua_binary_read_results.log`
- `opcua_binary_status_code_detail.log`
- `opcua_binary_variant_data.log`
- `opcua_binary_variant_metadata.log`

> **備考（ポート番号の変更について）**
> OPC UAサーバーがデフォルトの4840番ポート以外を使用している場合は、Zeekの設定ファイル（`/opt/zeek/share/zeek/site/local.zeek`）に以下を追記し、使用するポートをZeekに指定して `zeekctl deploy` を再実行する必要がある（以下は5000番の例）。
> ```zeek
> redef dpd_config += { [[5000/tcp]] = {"OPCUA_Binary"} };
> ```

---

## 6. Modbusのログ取得手順

Zeekは標準でModbus TCPプロトコルの基本的な解析に対応しているが、詳細な監視（機能コードやレジスタの読み書き等）を行う場合は、CISA提供の専用プラグインを導入する。

### 6.1 MonitorServerのIPアドレスの設定（Modbus環境用）
MonitorServerのIPアドレスをModbus環境（10.7.2.0/24）に合わせて変更する。Ubuntu 24.04 Server版では、`/etc/netplan/99-netcfg.yaml` を編集する。

```yaml
    enp0s3:
      dhcp4: false
      addresses:
        - 10.7.2.32/24
```
変更後、以下のコマンドで設定を適用し、反映を確認する。

```bash
sudo netplan apply
ip addr show
```

### 6.2 Modbusプラグインのインストール
CISA提供のModbusプラグインをインストールする。

```bash
sudo /opt/zeek/bin/zkg install https://github.com/cisagov/icsnpp-modbus
```
- testでエラーが発生しインストールを強制する場合は `--skiptests` オプションを使用する。

### 6.3 Modbus動作確認手順
ZeekとModbus各コンポーネントを連携させ、通信解析とログ出力をテストする。

**【手順1】Modbusサーバ（シミュレータ）の起動**
Modbusサーバが稼働するゲストOSで、Modbus TCPポート（デフォルト: 502）を開放して待機させる。`modbus-lab` 環境では、`sudo docker compose up -d` コマンドを実行するだけで、サーバ/クライアントが自動起動し、定期的な通信が発生する。

**【手順2】Modbusクライアントからの通信発生**
別のゲストOS等からModbusサーバへリクエストを送信し、通信イベントを発生させる。以下のコマンドで実際の通信（ポート502）を併せて確認できる。確認したらCtl-Cでtcpdumpを停止する。

```bash
sudo tcpdump -i enp0s3 -n -A tcp port 502
```

**【手順3】プラグインの適用（zeekctl deploy）**
インストールしたModbusプラグインを稼働中のZeekに反映させる。

```bash
sudo /opt/zeek/bin/zeekctl deploy
```

**【手順4】Zeekログの出力確認（ZeekゲストOS）**
`/opt/zeek/logs/current/` 内に以下のログが生成されていることを確認する。
- `modbus.log`
- `modbus_detailed.log`

---

## 7. BACnetのログ取得手順

### 7.1 MonitorServerのIPアドレスの設定（BACnet環境用）
MonitorServerのIPアドレスをBACnet環境（10.7.3.0/24）に合わせて変更する。Ubuntu 24.04 Server版では、`/etc/netplan/99-netcfg.yaml` を編集する。

```yaml
    enp0s3:
      dhcp4: false
      addresses:
        - 10.7.3.32/24
```
変更後、以下のコマンドで設定を適用し、反映を確認する。

```bash
sudo netplan apply
ip addr show
```

### 7.2 BACnetプラグインのインストール
CISAが提供している BACnet プラグインをダウンロードし、ビルド・インストールする。

```bash
sudo /opt/zeek/bin/zkg install https://github.com/cisagov/icsnpp-bacnet
```
- testでエラーが発生しインストールを強制する場合は `--skiptests` オプションを使用する。

### 7.3 BACnet動作確認手順
ZeekとBACnetの各コンポーネント（サーバ、クライアント）を仮想ネットワーク内で連携させ、実際に通信を発生させてログの出力を確認する。

> **注意**: 以下の手順に記載されているネットワークインターフェース名 `enp0s3`、 およびbacnet-stack-0.8.2のインストールパス名 `~/bacnet/bacnet-stack-0.8.2` は、適宜実環境に合わせて変更する。

**【手順1】プラグインの適用（zeekctl deploy）**
インストールしたBACnetプラグインを稼働中のZeekに反映させる。

```bash
sudo /opt/zeek/bin/zeekctl deploy
```

**【手順2】BACnetサーバ（ゲストOS）での実行**
サーバが稼働するゲストOSで以下のコマンドを実行し、BACnetサーバをデバイスID `1234` で待機させる。

```bash
export BACNET_IFACE=enp0s3
~/bacnet/bacnet-stack-0.8.2/bin/bacserv 1234
```

**【手順3】BACnetクライアント（ゲストOS）での通信発生**
クライアント用のゲストOSから以下のコマンドを実行し、ネットワーク内のBACnetデバイスを探索（Who-Isブロードキャスト）して通信を発生させる。

```bash
export BACNET_IFACE=enp0s3
~/bacnet/bacnet-stack-0.8.2/bin/bacwi -1
```

**【手順4】Zeekログの出力確認（ZeekゲストOS）**
通信発生後、`/opt/zeek/logs/current/` ディレクトリ内に、以下のログファイルが新しく生成されていることを確認する。
- `bacnet.log`
- `bacnet_discovery.log`

これらのファイルが存在すれば、Zeekが正常にBACnetプロトコルを検知・解析し、構築が完了していることになる。

---

## 8. 運用および応用設定

### 8.1 サーバー再起動時のZeek手動起動手順

本手順書ではZeekのOS起動時における自動起動（デーモン化）設定をあえて行なっていないため、MonitorServerを再起動（または停止状態から起動）した際は、毎回手動でZeekプロセスを起動させる必要がある。

```bash
# Zeekを通常起動する
sudo /opt/zeek/bin/zeekctl start

# 状態を確認し、"running" になっていることを確認する
sudo /opt/zeek/bin/zeekctl status
```

> **参考:** `deploy` コマンドは設定の変更やプラグイン追加時に使用するコマンドであるため、単なるOS再起動後のプロセス立ち上げであれば `start` コマンドを使用するのが最も適切である。
> （なお、`deploy` コマンドの内部処理の最後にも `start` が実行される。）

### 8.2 複数プロトコルの同時監視について
zeekctlによる常駐運用環境では、ZKG（パッケージマネージャー）を通じてインストールされたプラグインは自動的にすべて読み込まれる仕組み（`@load packages`）になっています。

そのため、EtherNet/IP、OPC UA、Modbus、BACnetのすべてのプラグインをインストールした状態で `zeekctl deploy` を実行しておけば、特別な起動オプション等を指定することなく、**すべてのプロトコルが自動的に同時監視**され、各プロトコルの通信が発生した際に、それぞれ対応するログ（`enip.log`, `opcua_binary.log`, `modbus.log`, `bacnet.log` 等）が同時に生成されます。

## 9. 補足

### 9.1 チェックサム・オフロードの影響と検証スキップについて
仮想環境や一部の物理NIC環境では、TCP/UDP/IPのチェックサムが「0」または不正確な値のままキャプチャされることがある。これはOSが計算をハードウェア（NIC）に任せる「チェックサム・オフロード」機能によるものである。

1. **オフロード機能**: OSは計算負荷を減らすため、チェックサム計算をNICに任せる。
2. **キャプチャのタイミング**: ZeekがNICに届く前の（未計算の）パケットを横取りするため、エラーとして検出される。
3. **Zeekの挙動**: デフォルトでは不正なチェックサムを持つパケットを破棄する。

特にVirtualBoxの内部ネットワーク等ではこの現象が顕著であるため、本手順書の「3.2 zeekctlを用いた初期設定と起動」の中で `local.zeek` に `ignore_checksums = T` を追記し、恒久的にチェックサム検証をスキップするアプローチを取っている。

### 9.2 Zeekは内部で監視するインターフェースをプロミスキャスモードにしている
そのため、zeekctlの実行前に、OS側でインターフェースのプロミスキャスモードを手動で有効化する設定は不要である。

### 9.3 インストール時のトラブルシューティング
パッケージのインストール（zkg install）中にプラグインの自動テストでエラー（Fail）となる場合がある。その場合でも、`--skiptests` オプションを付けて強制的にインストールすることで、実際には正常に動作することが多い。

### 9.4 Zeek実行時のトラブルシューティング
Zeekでlogファイルが生成されない場合、通信がキャプチャできるかを以下のtcpdumpコマンドで確認する。

```bash
sudo tcpdump -i <インターフェース名> -n port <ポート番号>
```

### 9.5 OpenSearch動作環境でZeekの設定を変える場合
OpenSearchスタック（OpenSearch等）と連携してログを収集している環境で、Zeekのプラグイン追加や `local.zeek` などの設定変更を行う場合、プロセス間の連携不具合やファイルロックによるエラーを防ぐため、以下の順序で停止・起動を行うことが推奨される。

> **備考**: OpenSearch や OpenSearch Dashboards は独立したシステムとして動作しているため、Zeekの設定変更に伴ってこれらを終了させる必要は通常はない。Zeekと同じサーバー内で稼働している「Filebeat」などの転送エージェントのみを停止すれば安全に変更が可能である。

**1. ログ転送・収集モジュールの停止とZeekの停止**
まず、Zeekのログを読み取っている転送エージェント（Filebeat等）を停止し、その次にZeek本体を停止する。
```bash
# Filebeatの停止
sudo systemctl stop filebeat

# Zeekの停止
sudo /opt/zeek/bin/zeekctl stop
```

**2. Zeekの設定変更**
プラグインのインストール（`zkg install`）や、設定ファイル（`local.zeek`等）の編集を行う。

**3. Zeekの起動と収集モジュールの再開**
設定を変更したZeekをデプロイして起動し、ログの出力準備が整ってから転送エージェント側を再開させる。
```bash
# Zeekの設定適用と起動
sudo /opt/zeek/bin/zeekctl deploy

# Filebeatの起動
sudo systemctl start filebeat
```

#### （参考）OpenSearchスタック全体もあわせて再起動する場合の手順
システム全体のメンテナンス等で、もし OpenSearch や OpenSearch Dashboards も含めてすべて終了・起動させる場合は、データの整合性を担保しエラーを防ぐため、以下の「外側から順に止め、内側から順に起動する」手順で実施する。

**【終了時の順序】**
データの入り口（末端）から先へ停止していく。
1. `sudo systemctl stop filebeat` （ログ転送の停止）
2. `sudo /opt/zeek/bin/zeekctl stop` （ログ生成の停止）
3. `sudo systemctl stop logstash` （※Logstashを使用している場合）
4. `sudo systemctl stop opensearch-dashboards` （画面表示・UIの停止）
5. `sudo systemctl stop opensearch` （データベース・本体の停止）

**【起動時の順序】**
データを受け止める土台（コア）から順に起動していく。
1. `sudo systemctl start opensearch` （※完全に起動するまで数十秒待機する）
2. `sudo systemctl start opensearch-dashboards`
3. `sudo systemctl start logstash` （※使用している場合）
4. `sudo /opt/zeek/bin/zeekctl deploy` （Zeekの稼働開始）
5. `sudo systemctl start filebeat` （ログ転送の再開）

以上