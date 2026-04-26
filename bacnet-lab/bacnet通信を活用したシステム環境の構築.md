# BACnet通信を活用したシステム環境の構築

本ドキュメントでは、Bacnetのオープンソース`bacnet-stack-0.8.2`のビルドから基本的な動作確認までの手順をまとる。
Ubuntuのバージョンは、bacnet-stack-0.8.2が動作するUbuntu18.04 desktopを使用する。

## 構成要素
| 種別 | 実装形態 | IPアドレス |
|---|---|---|
| BacnetServer | Ubuntu18.04 desktop | 10.7.3.36 |
| BacnetClient | Ubuntu18.04 desktop | 10.7.3.37 |

Bacnet通信はbroadcastを多様するため、サーバとクライアントのゲストOSを内部ネットワークに個別に配置する実装とした。一台のゲストOS上でのDockerによるサーバ・クライアントの実装は、ブロードキャストがエミュレートされないリスクがあるため、採用しない。

## 0. VirtualBoxおよびBanet server/clientの事前準備

VirtualBoxへUbuntu18.04 desktopを2台インポートし、ネットワークの構成を行う。以下は、Windowsホスト側（PowerShell）の操作と、Ubuntu18.04 desktop内（ターミナル）の操作を含む。

2. Virtualboxの **内部ネットワーク(intnet7.3)へのDHCPサーバーの割り当て**
   `10.7.3.128` から（`10.7.3.191` まで）のアドレスをDHCPで割り当てる内部ネットワーク（`intnet7.3`）を作成する。
   ```powershell
   .\VBoxManage dhcpserver add --netname intnet7.3 --ip 10.7.3.2 --netmask 255.255.255.0 --lowerip 10.7.3.128 --upperip 10.7.3.191 --enable
   ```

### Bacnet serverの場合
1. **Ubuntu18.04 desktopの読み込み（インポート）**(Bacnet Server分)
   ダウンロードしたUbuntu18.04 desktopのイメージ（`ubuntu-18.04.6-desktop-amd64.iso`）をVirtualBoxに読み込む。GUIからの追加・インポート、または以下のコマンド例を使用する。
   ```powershell
   VBoxManage import "C:\Users\seched\Downloads\ubuntu-18.04.6-desktop-amd64.iso"
   ```

3. **Bacnet Serverのアダプタ設定（GUIでの実施）**
   VirtualBoxのGUIからアダプタを割り当てる。
   1. VirtualBoxのメイン画面で対象のVM（例:`Banet server 18.04 desktop`）を選択し、「設定」>「ネットワーク」を開く。
   2. **「アダプター 1」**タブを開き、「ネットワークアダプターを有効化」にチェックを入れる。
      - **割り当て:** `内部ネットワーク`
      - **名前:** `intnet7.3`
   3. **「アダプター 2」**のタブを開き、「ネットワークアダプターを有効化」にチェックを入れる。
      - **割り当て:** `NAT`
   - ポートフォワーディング
     名前:SSH, プロトコル:TCP, ホストポート:7336, ゲストポート:22
   ※ポートフォワーディングは、インターネット接続とホストOSとのSSHに用いる。開発時のみ有効とする。
4. 「OK」を押して保存する。


5. **Banet serverへの静的IPアドレスの設定**
   仮想マシンを起動後、Banet server内でインターフェースのIPアドレスをNetworkManagerを用いて静的に設定する。NetworkManager(`nmcli`)を使用する。

   インターフェース（OS認識名）と、対応するVirtualBoxのアダプタ割り当ては以下の通り：
   - **第1インターフェース** (アダプタ 1 / 内部ネットワーク) : `10.7.3.36` (例 `eth0`)
 

   ```bash
   # Banet serverのターミナルで実行
   
   まず、以下のコマンドで現在のインターフェース名とNetworkManagerの接続名を確認する。
   ```bash
   # インターフェース名（eth0, eth1 等）とアサインされているIPアドレスの確認
   ip addr show

   # インターフェース名に対応する接続名（Wired connection 1 等）の確認
   nmcli connection show
   ```

   # 第1インターフェースへのIP設定
   sudo nmcli connection modify "Wired connection 1" ifname eth0 ipv4.method manual ipv4.addresses 10.7.3.36/24
   sudo nmcli connection up "Wired connection 1"
   ```

6. **sshの起動時の自動起動化、起動、状態の確認**
   Banet server内でSSHサーバーを起動し、さらにOS起動時に自動で立ち上がるように設定する。これにより、次回以降のVM起動時には自動的にSSHが有効になる。
   ```bash
   # 自動起動を有効化
   sudo systemctl enable ssh
   # サービスを起動
   sudo systemctl start ssh
   # 状態の確認
   sudo systemctl status ssh
   #ssh接続確認
   ssh -p 7336 kali@127.0.0.1
   ```

7. **Banet serverのタイムゾーン設定（Asia/Tokyo）**
ログのタイムスタンプを日本時間（JST）に合わせるため、タイムゾーンを `Asia/Tokyo` に変更する。
   ```bash
   sudo timedatectl set-timezone Asia/Tokyo
   ```

## 1. ソースコードの入手

ソースコードのダウンロードに必要なため、マシンのネットワークを **NAT** に設定して起動します。

```bash
# 作業ディレクトリの作成と移動
mkdir -p ~/bacnet
cd ~/bacnet

# Subversion のインストール
sudo apt install subversion

# bacnet-stack 0.8.2 のソースコードをチェックアウト
svn checkout http://svn.code.sf.net/p/bacnet/code/tags/bacnet-stack-0.8.2/
cd ./bacnet-stack-0.8.2
```

## 2. ビルドの実行
対象ディレクトリで以下のコマンドを実行し、通常ビルド（デバッグビルド以外）を行います。
```bash
make clean all
```

## 3. ネットワーク環境の変更（内部ネットワーク）
ローカル環境での通信検証のために、ネットワークを **内部ネットワーク** に変更します。

```bash
# ネットワーク設定変更のためシャットダウン
shutdown -h now
```

1. 仮想環境などの設定画面から、ネットワークを「内部ネットワーク」に変更します。
2. システムを起動します。
3. 起動後、割り振られたIPアドレスとインターフェース名を確認します。

```bash
# インターフェース名（eth0, eth1 等）とアサインされているIPアドレスの確認
ip addr show
```

**出力例 (enp0s3 の場合):**
```text
enp0s3: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 10.7.3.36  netmask 255.255.255.0  broadcast 10.7.3.255
```

## 4. サーバ実行と動作確認
ビルドして生成されたバイナリ (`bacserv`) を起動します（引数の `1234` は Device ID）。

```bash
# インターフェースを指定しサーバ実行
export BACNET_IFACE=enp0s3
~/bacnet/bacnet-stack-0.8.2/bin/bacserv 1234
```


### Bacnet clientの場合

1. **Ubuntu18.04 desktopの読み込み（インポート）**
   (同上)

2. **Bacnet Serverのアダプタ設定（GUIでの実施）**
   VirtualBoxのGUIからアダプタを割り当てる。
   1. VirtualBoxのメイン画面で対象のVM（例:`Banet Client 18.04 desktop`）を選択し、「設定」>「ネットワーク」を開く。
   2. **「アダプター 1」**タブを開き、「ネットワークアダプターを有効化」にチェックを入れる。
      - **割り当て:** `内部ネットワーク`
      - **名前:** `intnet7.3`
   3. **「アダプター 2」**のタブを開き、「ネットワークアダプターを有効化」にチェックを入れる。
      - **割り当て:** `NAT`
   - ポートフォワーディング
     名前:SSH, プロトコル:TCP, ホストポート:7337, ゲストポート:22
   ※ポートフォワーディングは、インターネット接続とホストOSとのSSHに用いる。開発時のみ有効とする。
4. 「OK」を押して保存する。


5. **Banet clientへの静的IPアドレスの設定**
   仮想マシンを起動後、Banet client内でインターフェースのIPアドレスをNetworkManagerを用いて静的に設定する。NetworkManager(`nmcli`)を使用する。

   インターフェース（OS認識名）と、対応するVirtualBoxのアダプタ割り当ては以下の通り：
   - **第1インターフェース** (アダプタ 1 / 内部ネットワーク) : `10.7.3.37` (例 `eth0`)
 

   ```bash
   # Banet serverのターミナルで実行
   
   まず、以下のコマンドで現在のインターフェース名とNetworkManagerの接続名を確認する。
   ```bash
   # インターフェース名（eth0, eth1 等）とアサインされているIPアドレスの確認
   ip addr show

   # インターフェース名に対応する接続名（Wired connection 1 等）の確認
   nmcli connection show
   ```

   # 第1インターフェースへのIP設定
   sudo nmcli connection modify "Wired connection 1" ifname eth0 ipv4.method manual ipv4.addresses 10.7.3.37/24
   sudo nmcli connection up "Wired connection 1"
   ```

6. **sshの起動時の自動起動化、起動、状態の確認**
   Banet client内でSSHサーバーを起動し、さらにOS起動時に自動で立ち上がるように設定する。これにより、次回以降のVM起動時には自動的にSSHが有効になる。
   ```bash
   # 自動起動を有効化
   sudo systemctl enable ssh
   # サービスを起動
   sudo systemctl start ssh
   # 状態の確認
   sudo systemctl status ssh
   #ssh接続確認
   ssh -p 7337 kali@127.0.0.1
   ```

7. **Banet clientのタイムゾーン設定（Asia/Tokyo）**
(同上)
   ```

## 1. ソースコードの入手
(同上)

## 2. ビルドの実行
(同上)

## 3. ネットワーク環境の変更（内部ネットワーク）
ローカル環境での通信検証のために、ネットワークを **内部ネットワーク** に変更します。

```bash
# ネットワーク設定変更のためシャットダウン
shutdown -h now
```

1. 仮想環境などの設定画面から、ネットワークを「内部ネットワーク」に変更します。
2. システムを起動します。
3. 起動後、割り振られたIPアドレスとインターフェース名を確認します。

```bash
# インターフェース名（eth0, eth1 等）とアサインされているIPアドレスの確認
ip addr show
```

**出力例 (enp0s3 の場合):**
```text
enp0s3: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 10.7.3.37  netmask 255.255.255.0  broadcast 10.7.3.255
```

## 4. クライアントの実行と動作確認
ビルドして生成されたバイナリ (`bacserv`) を起動します（引数の `1234` は Device ID）。

```bash
# インターフェースを指定しサーバ実行
export BACNET_IFACE=enp0s3
~/bacnet/bacnet-stack-0.8.2/bin/bacwi -1
```
