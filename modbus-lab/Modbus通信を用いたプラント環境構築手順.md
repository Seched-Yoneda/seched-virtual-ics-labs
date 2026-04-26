# Modbus通信を用いたプラント環境構築手順

Ubuntu 24.04 Server上にModbus通信を用いたプラント環境を構築する手順を記載する。

## 構成要素
| 種別 | 用途 | 実装形態 |
|---|---|---|
| modbusサーバ | PLC for BPCS | Ubuntu24.04上のdocker |
| modbusクライアント | OCS（SCADA) | Ubuntu24.04上のdocker |

## ソースプログラムの構成

本構成では、ホスト側にあるソースプログラムをビルドしてコンテナ化することで、シミュレーション環境を動作させている。それぞれのスクリプトに実装されている処理の概要は以下の通りである。

### 1. `plc/server.c` （PLC・Modbusサーバ）
* **言語/ライブラリ**: C言語 (`libmodbus`)
* **実装概要**: ガスプラントの機器（センサーやバルブなど）に見立てたModbus TCPサーバである。内部のメモリ領域（レジスタ・コイル等）に各種の現在状態やパラメーターを保持しており、SCADAからの要求（クエリ）に対して値を返信したり、上書き保存したりする。
* **拡張性**: このプログラム内に「バルブ操作に応じて液位が変化する」といった物理方程式を付け足すことで、より本格的なプラントシミュレータに進化させることができる。

### 2. `scada/app.py` （SCADA・Modbusクライアント）
* **言語/ライブラリ**: Python (`Flask`, `pymodbus`)
* *(※ `scada/templates/index.html` がGUIのフロントエンドを務める)*
* **実装概要**: Webサーバー兼Modbusクライアントとして動作する通信の仲介役である。
* **定期読み取り（監視）**: 数秒ごとにPLCエミュレータ（10.7.2.37:502）へアクセスして各種数値をまとめて取得（ポーリング）し、Web（JavaScript）へJSONとして配信する。
* **書き込み（操作）**: 画面上の操作によって設定変更が行われると、その設定値をPLCの保持レジスタへ即座に書き込みに行く。

---

## 1. VirtualBoxおよびUbuntu24.04 serverの事前準備

### 1.1 ソフトウェアのダウンロード
1. **VirtualBoxのダウンロード・インストール**
   - [VirtualBox公式サイト](https://www.virtualbox.org/)からWindowsホスト用のインストーラーをダウンロードし、インストールする。
2. **Ubuntu 24.04 LTS ServerのISOイメージを取得**
   - [Ubuntu公式ダウンロードページ](https://ubuntu.com/download/server)から `Ubuntu 24.04.x LTS Server` のISOイメージ（.isoファイル）をダウンロードする。

### 1.2 Ubuntu24.04 serverの読み込み（インポート）
   
   1. VirtualBoxを起動し、「新規」をクリックする。
2. 名前（`PlantDockerHost Ubnntu24.04 server`）、ISOイメージ（先ほどダウンロードしたUbuntuのISOを選択）を設定し、「自動インストールをスキップ（※推奨）」にチェックを入れて「次へ」進む。
3. **ハードウェア**:
   - メモリ(RAM): **4096 MB** (4GB) 以上を推奨
   - プロセッサ: **2 CPU** 以上を推奨
4. **ハードディスク**:
   - 仮想ハードディスクを作成: **40 GB** 以上を割り当てて「次へ」→「完了」。

### 1.3 Ubuntu24.04 serverのアダプタ設定（GUIでの実施）
   VirtualBoxのGUIからアダプタを割り当てる。
   1. VirtualBoxのメイン画面で対象のVM（PlantDockerHost Ubnntu24.04 server）を選択し、「設定」>「ネットワーク」を開く。
   2. **「アダプター 1」**タブを開き、「ネットワークアダプターを有効化」にチェックを入れる。
      - **割り当て:** `内部ネットワーク`
      - **名前:** `intnet7.2`
   3. **「アダプター 2」**のタブを開き、「ネットワークアダプターを有効化」にチェックを入れる。
      - **割り当て:** `NAT`
      - ポートフォワーディング
        名前:SSH, プロトコル:TCP, ホストポート:7236, ゲストポート:22
      ※ポートフォワーディングは、インターネット接続とホストOSとのSSHに用いる。開発時のみ有効とする。
   4. 「OK」を押して保存する。

### 1.4 内部ネットワーク(intnet7.2)へのDHCPサーバーの割り当て
   内部ネットワーク（`intnet7.2`）には、`10.7.2.128` から（`10.7.2.191` まで）のアドレスをDHCPで割り当てる。10.7.2.3から10.7.2.127を静的IPアドレス割り当てレンジとする。

   ```powershell
   .\VBoxManage dhcpserver add --netname intnet7.2 --ip 10.7.2.2 --netmask 255.255.255.0 --lowerip 10.7.2.128 --upperip 10.7.2.191 --enable
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

### 1.7 PlantDockerHost Ubuntu24.04 server内での静的IPアドレスの設定
   仮想マシンを起動後、`/etc/netplan/` 配下のyamlファイルを用いて各インターフェースのIPアドレスを静的に設定する。

   インターフェース名の確認
   ```bash
   ip addr show
   ```

   インターフェース名は、`enp0s3` (内部ネットワーク) と `enp0s8` (NAT) とする（※適宜読み替えること）。
   `/etc/netplan/99-netcfg.yaml` を作成・編集する。

   ```bash
   sudo nano /etc/netplan/99-netcfg.yaml
   ```

   **記述内容:** (PlantDockerHostなのでIPは 10.7.2.36 とする)
   ```yaml
   network:
     version: 2
     renderer: networkd
     ethernets:
       # --- Adapter 1: Internal Network (intnet7.2) ---
       enp0s3:
         dhcp4: false
         addresses:
           - 10.7.2.36/24
         # nameservers:
         #   addresses: [10.7.2.1] # Use internal DNS if available in the future
   
       # --- Adapter 2: NAT (for Host-to-Guest SSH) ---
       enp0s8:
         dhcp4: true
   ```
   保存後、設定を反映させる。
   ```bash
   sudo netplan apply
   ```
      ホストOSの端末から以下でログインできることを確認する。
   ```bash
   ssh -p 7236 kali@127.0.0.1
   ```

### 1.8 PlantDockerHost Ubuntu24.04 serverのタイムゾーン設定（Asia/Tokyo）
   ログのタイムスタンプを日本時間（JST）に合わせるため、タイムゾーンを `Asia/Tokyo` に変更する。
   ```bash
   sudo timedatectl set-timezone Asia/Tokyo
   ```
---

## 2. ゲストOS上へのDocker環境の構築

### 2.1 パッケージの更新
```bash
sudo apt update
sudo apt upgrade -y
```

### 2.2 Dockerの公式GPGキーとリポジトリの追加
Ubuntu標準のDockerではなく、Docker公式の最新版をインストールする。
```bash
# 必須パッケージのインストール
sudo apt install -y ca-certificates curl

# Docker公式のGPGキーを追加
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# AptリポジトリにDockerを追加
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# パッケージリストを更新 
sudo apt update
```

### 2.3 DockerおよびDocker Composeのインストール
```bash
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 2.4 インストールの確認
```bash
sudo docker --version
sudo docker compose version
```
それぞれバージョン情報が表示されれば、Docker環境の構築は完了。

---

## 3. プロジェクトの構成と docker-compose.yml の作成

今回、各Dockerコンテナ（Modbusサーバ、クライアント）には、**Macvlanネットワーク**を使用してVirtualBoxのUbuntuホストと同じサブネットのIPアドレスを直接割り当てる。これにより、外部（Kali Linuxなど）からコンテナへIP通信（pingやModbus通信）が可能となる。

 ### 3.1 プロジェクトディレクトリへの移動
```bash
# （プロジェクト用ディレクトリに移動する）
cd /home/kali/localwork/plant
```

### 3.2 docker-compose.yml の作成
プロジェクトディレクトリ内に、以下の内容で `docker-compose.yml` を作成する。
（※ `parent: enp0s3` の部分は、`ip a`コマンドで確認したUbuntuのメインインターフェース名に合わせて変更すること。）

```yaml
services:
  # 1. PLC for BPCS (Modbus Server 1)
  modbus-bpcs:
    build: ./plc
    container_name: modbus-bpcs
    networks:
      scada-net:
        ipv4_address: 10.7.2.37

  # 3. OCS/SCADA (Modbus Client)
  scada-client:
    build: ./scada
    container_name: scada-client
    ports:
      - "5000:5000"
    volumes:
      - ./scada:/app
    environment:
      - PLC_IP=10.7.2.37
    depends_on:
      - modbus-bpcs
    networks:
      scada-net:
        ipv4_address: 10.7.2.39

networks:
  scada-net:
    driver: macvlan
    driver_opts:
      # Ubuntuのメイン・ネットワークインターフェース（ifconfigで確認）を指定する
      parent: enp0s3
    ipam:
      config:
        - subnet: 10.7.2.0/24
          # コンテナ用IPプールを予備領域(240〜255)に逃すことで他の静的IPとの干渉を回避
          ip_range: 10.7.2.240/28
```

---

## 4. コンテナの起動と疎通確認

コンテナを起動し、ホストOSや別マシンのKali Linuxなどからコンテナに直接通信できるか確認する。
プロジェクトディレクトリで以下のコマンドを実行する。

```bash
# 古いネットワークの競合がある場合は削除（必要に応じて）
# sudo docker network prune -f

# コンテナのビルドおよびバックグラウンド起動
# （プロジェクト用ディレクトリに移動）
cd /home/kali/localwork/plant
sudo docker compose build
sudo docker compose up -d
```
内部ネットワークに接続された他のマシンからのmacvlanに接続されたdockerが通信を受信するために、プロミスキャスモードを有効にする。
```bash
sudo ip link set dev enp0s3 promisc on
```

起動したら、内部ネットワーク上の他の仮想OS(Kali Linuxなど)から各コンテナのIPアドレス宛てに `ping` を打って疎通通信ができるか確認する。
* BPCS（Modbusサーバ1）: **10.7.2.37**
* SCADAクライアント: **10.7.2.39**

```bash

ping -c 4 10.7.2.37
ping -c 4 10.7.2.39
```

応答が正しく返ってくれば、Macvlanネットワークを使ったプラント環境の構築は完了

## 5. Kali linuxでのSCADA HMIの表示

プラントのSCADAサーバは、GUIのベースとなる `index.html` と、プラントの現在値を配信するAPIを持っている。
内部ネットワーク上のKali Linuxのブラウザでこの `index.html` にアクセスすると、ブラウザ上で動くプログラム（JavaScript）がSCADAから動的にデータを取得し続け、画面の表示をリアルタイムに更新する仕組みである。

Kali linuxのFireFoxにて
http://10.7.2.39:5000
によりSCADAのHMIを表示させ、kali linuxの画面をRDPでホストOSに表示することでHMIが表示されることを確認する。

### 5.1 Windows11のホストOSからkali linuxにRDPで接続する。

Windows 11のホストOSからKali Linuxにリモートデスクトップ(RDP)で接続するための設定手順を示す。

#### 5.1.1 xrdpのインストール状態確認
kali linuxにて、xrdpが既にインストールされているか、バージョンを表示させて確認する。
```bash
xrdp -v
```
バージョン情報（例：`xrdp 0.9.21.1` など）が表示されればインストール済み。「コマンドが見つかりません」と出た場合は以下手順でインストールする。

#### 5.1.2 ネットワーク設定の追加（インターネット接続用）
xrdpをインストールするためにインターネット接続が必要となる。VirtualBoxの設定で一時的に**NAT接続**などを追加し、インターネットに繋がるようにして再起動する。

#### 5.1.3 xrdpのインストールと有効化
インターネットに繋がったら、KaliLinuxにて以下のコマンドを実行する。
```bash
sudo apt update
sudo apt install -y xrdp

# サービスの有効化と開始
sudo systemctl enable xrdp
sudo systemctl start xrdp
```

#### 5.1.4 起動状態の確認
サービスが正常に動作しているか確認する。
```bash
systemctl status xrdp
```

#### 5.1.5 セッション情報の作成
Kali Linuxにて、RDP接続時にXFCEデスクトップが起動するように設定する。
```bash
echo "xfce4-session" > ~/.xsession
```

#### 5.1.6 Firefoxでの入力問題の対処
Firefoxのハードウェアアクセラレーションが有効な場合、RDP経由での入力（Enterキーが効かない等）に問題が発生することがある。その場合は以下の設定を行い、「ソフトウェア描画」に切り替える。

**設定手順：**
- 設定項目 `layers.acceleration.disabled` を `true` にする
- 設定項目 `gfx.webrender.software` を `true` にする

**一括設定ワンライナー：**
```bash
find ~/.mozilla/firefox/ -name "prefs.js" -exec sh -c "echo 'user_pref(\"layers.acceleration.disabled\", true);' >> {}; echo 'user_pref(\"gfx.webrender.software\", true);' >> {}" \;
```

設定完了後、kail Linuxのローカルでログアウトし、Windows 11の「リモートデスクトップ接続」からKali LinuxのIPアドレス　192.168.56.7 を指定して接続する。
接続し、Kali linuxのFireFoxにて
http://10.7.2.39:5000　にて画面が確認できれば、PLC/SCADAの動作確認は完了。Kali linuxをシャットダウンし、NAT接続を無効化する。

## 6. モニターサーバー（IDS等）での通信パケットキャプチャ設定

プラントのサイバーセキュリティ演習では、ネットワークの通信を監視・分析するためのモニターサーバー（IDS: 侵入検知システムなど・例: `10.7.2.32`）を設置する。

今回の構成では「DockerのMacvlanネットワーク」を利用しており、同一ホスト（Kali/Ubuntu）内で稼働するコンテナ同士（`10.7.2.37` と `10.7.2.39`）の通信は、物理的なネットワークインターフェース（例: `enp0s3`）の外に送出されず、Linuxカーネル内部の仮想Macvlanスイッチ内で直接折り返されて通信が完結する。

このため、**VirtualBoxの内部ネットワーク（Internal Network）側には一切パケットが流れない**という事象が発生し、モニターサーバーのインターフェースに通信パケットが到達しない。

そこで、**物理環境における「L2スイッチのミラーポート（SPANポート）」をソフトウェア的に再現する**ため、Linuxカーネル標準の機能（`iptables TEE` ターゲットによるパケット複製）を利用する。以下に手順を示す。

### 6.1 設定手順（iptables TEEによるパケット複製）

ここでは `10.7.2.39`（SCADAコンテナ）のネットワーク名前空間に入り込み、Modbus通信パケット（TCP 502番ポート）の完全なコピーをモニターサーバー（`10.7.2.32`）へ複製・送信するルールを追加する。

**1. Dockerホスト側でポートミラーリングルールを追加する**
以下のコマンドを実行し、`scada-client` コンテナの出入口にルールを適用する。

```bash
# SCADAクライアントから送信されるリクエスト（宛先ポート502）のコピーをモニターサーバーへ転送
sudo nsenter -t $(sudo docker inspect -f '{{.State.Pid}}' scada-client) -n \
  iptables -t mangle -A POSTROUTING -p tcp --dport 502 -j TEE --gateway 10.7.2.32

# SCADAクライアントへ返ってくるレスポンス（送信元ポート502）のコピーをモニターサーバーへ転送
sudo nsenter -t $(sudo docker inspect -f '{{.State.Pid}}' scada-client) -n \
  iptables -t mangle -A PREROUTING -p tcp --sport 502 -j TEE --gateway 10.7.2.32
```

**2. モニターサーバー側でのキャプチャ確認**
モニターサーバー（`10.7.2.32`）の端末で、`tcpdump` などを実行して通信がプロミスキャスモードにしたインタフェースで取得できることを確認する

```bash
# 対象のインターフェース（例：enp0s3）をプロミスキャスモードに設定
sudo ip link set dev enp0s3 promisc on

# モニターサーバー側のインターフェース上でキャプチャを実行
sudo tcpdump -i enp0s3 -n port 502
```

この設定により、パケットダンプや侵入検知システム（Snort、Suricata等）で、物理的なミラーポートを介しているのと全く同じように生トラフィックを監視させることが可能になる。


> [!IMPORTANT]
> **設定の揮発性について**
> この `iptables` によるミラーリング機能はメモリ上の設定である。そのため、**OS（ホストマシン）の再起動や、コンテナの再起動・再作成を行うたびに設定が消去される。**
> 通信を再度キャプチャしたい場合は、コンテナが起動した後に毎回必ず同じ手順（上記コマンドの実行）を実施する必要がある。

※手動でミラーリング設定を解除したい場合は、コンテナを再起動するか、上記コマンドの `-A` を `-D` に置き換えて実行する。

---

## 7. 補足

### 7.1 Dockerコマンドをsudoなしで実行する方法

毎回 `sudo` を付ける手間を省きたい場合は、現在のユーザーを `docker` グループに追加することで、`sudo` なしでDockerコマンドを実行できるようになる。

```bash
sudo usermod -aG docker $USER
```

※設定を反映させるために、一度 `exit` でログアウトして再度SSHでログインし直すか、`newgrp docker` コマンドを実行すること。

---

### 7.2 Macvlanのプロミスキャスモードについて

Macvlanを使用する場合、Dockerホストの使うインターフェース（例: `enp0s3`）を**プロミスキャスモード**にしておく必要がある。以下のコマンドで有効化し、確認する。

```bash
# インターフェース名（enp0s3）は適宜の環境に合わせて変更
sudo ip link set dev enp0s3 promisc on

# state UP ... のあとに PROMISC が追加されていることを確認
sudo ip addr show enp0s3
```

### 7.3 なぜプロミスキャスモードが必要なのか？

通常、ネットワークインターフェース（LANカード）は「自分自身のMACアドレス宛てのパケット」のみを受信し、それ以外は破棄する仕組みになっている。しかし、DockerのMacvlanネットワークを使用する場合、1つの物理（または仮想）ネットワークインターフェース上に、「コンテナごとに異なる仮想的なMACアドレス」が複数作成される。

プロミスキャスモード（無差別モード）を有効にすることで、インターフェースが「自分宛てではないMACアドレス（＝各コンテナ宛て）のパケット」も破棄せずに受信できるようになり、外部からの通信が正常にコンテナまで届くようになる。

---