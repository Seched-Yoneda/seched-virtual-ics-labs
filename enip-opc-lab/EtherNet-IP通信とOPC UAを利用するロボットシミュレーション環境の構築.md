# EtherNet/IP通信とOPC UAを利用するロボットシミュレーション環境の構築 (Docker活用)

本ドキュメントでは、オープンソースを用いて構築した「OPC UAおよびEtherNet/IP環境のMES-PLC-ロボット連携シミュレーション」を、DockerおよびDocker Composeを活用してネットワーク設定やプロセスの起動・終了を自動化した実行手順を定義する。

## 1. 動作環境とアーキテクチャ概要

| 項目 | 内容 |
| --- | --- |
| **OS環境** | Ubuntu 24.04 Desktop (VirtualBox仮想マシン上: FADockerHost) |
| **開発言語** | Python 3.12 |
| **MES (コンテナ)** | `fa_sim_mes` / `10.7.1.40`<br>OPC UA Serverとして生産オーダーや状態を管理する。 |
| **HMI (コンテナ)** | `fa_sim_hmi` / `10.7.1.41`<br>Webダッシュボード(HTTP 8080)を提供し、OPC UAおよびEtherNet/IP Clientとして稼働する。 |
| **PLC (コンテナ)** | `fa_sim_plc` / `10.7.1.42`<br>OPC UA Client および EtherNet/IP Client/Server としてMESとRobot間の橋渡しを行う。 |
| **Robot (コンテナ)** | `fa_sim_robot` / `10.7.1.43`<br>EtherNet/IP Server。内部でPyBullet物理エンジンを起動し、ホスト側のディスプレイに3D描画を行う。 |

**アーキテクチャ概要:**
ホストOS内にDockerの `macvlan` ネットワーク (`10.7.1.x`) を構築し、MES、HMI、PLC、Robotの4つをすべて独立したコンテナとして立ち上げる。これらはOPC UAおよびEtherNet/IPプロトコルを用いて相互通信し、実際の工場環境に近いネットワーク構成と連動動作を仮想空間で再現している。

---

## 2. 【初回のみ】新規サーバーでの初期構築手順（ゼロから構築する場合）

Ubuntu 24.04サーバーに新規に環境を構築する場合は、シミュレーションを実行する前に以下の事前準備を行う。

### 事前準備 1. 必須パッケージとDockerのインストール
Ubuntuの初期状態から、Docker関連をインストールする。
```bash
sudo apt update
sudo apt install -y docker.io docker-compose
```

### 事前準備 2. ネットワークインターフェース名の確認と修正（重要）
環境によってmacvlanの親となるネットワークインターフェース名（例: `enp0s3`, `eth0`, `ens33` 等）が異なる。
1. `ip a` コマンドを実行して、現在メインで通信しているIPが割り当てられたインターフェース名を確認する。
2. もし `enp0s3` 以外だった場合は、あらかじめ `docker-compose.yml` の `parent: enp0s3` などの該当箇所を実際のインターフェース名に書き換える。

### 事前準備 3. 画面スリープおよびロックの無効化
PyBulletのGUI描画処理と競合してホストOS全体がフリーズする（X Window Systemのクラッシュ）のを防ぐため、以下のコマンドでスリープとロック機能を無効化する。
```bash
gsettings set org.gnome.desktop.session idle-delay 0
gsettings set org.gnome.desktop.screensaver lock-enabled false
```

---

## 3. シミュレーションの実行手順（日々の起動・終了）

すべてのシステムプロセスはDockerコンテナ化されているため、操作は基本的にプロジェクトディレクトリ上で完結する。

### Step 1. ホスト側ネットワークのプロミスキャス設定
外部（Kali Linux等）との直接通信や、ポートミラーリングパケットを正常に受信するため、親インターフェース `enp0s3` をプロミスキャスモードに変更する。（OS再起動ごとに実行が必要である）
```bash
sudo ip link set enp0s3 promisc on
```

### Step 2. 環境設定スクリプトの実行 (GUI描画連携用)
FADockerHost上で、コンテナ内のPyBulletがホスト側のディスプレイへ描画できるようにアクセス許可（`xhost`）とディスプレイ番号の環境変数設定を行う。
```bash
cd ~/localwork/opc_enip
./start.sh
```

### プロジェクト構成と各種ファイルの配置

本シミュレーション環境は、各コンポーネント（HMI、MES、PLC、Robot）ごとにディレクトリが分割されており、それぞれの内部に専用の `Dockerfile` とソースコードが配置されている。

```text
opc_enip/
 ├── docker-compose.yml   # ネットワークおよび全4コンテナの起動・依存関係の定義
 ├── start.sh             # GUI描画権限(xhost)とディスプレイ環境変数の自動設定スクリプト
 ├── hmi/                 # HMIコンテナ用ディレクトリ
 │   ├── Dockerfile
 │   ├── app.py           # WebダッシュボードUIおよびOPC UA/ENIP通信処理
 │   ├── requirements.txt
 │   ├── static/
 │   │   └── css/
 │   │       └── index.css # Web画面用のスタイルシート
 │   └── templates/
 │       └── index.html   # Web画面用のHTMLテンプレート
 ├── mes/                 # MESコンテナ用ディレクトリ
 │   ├── Dockerfile
 │   ├── main.py          # OPC UA Serverの実装（オーダー管理等）
 │   └── requirements.txt
 ├── plc/                 # PLCコンテナ用ディレクトリ
 │   ├── Dockerfile
 │   ├── main.py          # ロジック制御（OPC UA Client 兼 ENIP制御）
 │   └── requirements.txt
 └── robot/               # Robotコンテナ用ディレクトリ
     ├── Dockerfile
     ├── main.py          # PyBullet物理シミュレーションとENIP通信処理
     └── requirements.txt
```

### Step 3. コンテナのビルドと起動

Docker Composeを使って、4つのコンテナを一連の依存関係に沿って一括起動する。
```bash
sudo docker-compose up -d --build
```
（※ソースコードの変更がなく、単に再起動するだけの場合は `--build` は不要である）

起動後、FADockerHost上にRobotのアーム画面が表示される。同時に、Kali Linuxなどの外部ブラウザから `http://10.7.1.41:8080/` にアクセスすることで、HMI画面を通じた操作と監視が可能となる。

### Step 4. シミュレーションの終了
演習が終了したら、不要なリソース消費を防ぐため、以下のコマンドで全コンテナと仮想ネットワークを停止・削除する。
```bash
sudo docker-compose down
```

---

## 4. モニターサーバー（IDS等）での通信パケットキャプチャ設定

DockerのMacvlanネットワークでは、同一ホスト内で稼働するコンテナ間の通信（例: `fa_sim_plc` と `fa_sim_mes` 間など）は外部の物理ネットワークに出力されない。そのため、モニターサーバー（例: `10.7.1.32`）でパケットを直接キャプチャすることができない。
これを解決するため、Linux標準の `iptables TEE` ターゲット機能を用いてソフトウェア的にミラーポートを再現する。

### 設定手順（iptables TEEによるパケット複製）

Dockerホストマシン（FADockerHost）上で以下のコマンドを実行し、各コンテナが送信するTCP通信（POSTROUTING）を複製してモニターサーバーへ転送する。

```bash
# 全4コンテナが送信するTCPパケットをモニターサーバーへ転送
for container in fa_sim_hmi fa_sim_mes fa_sim_plc fa_sim_robot; do
  sudo nsenter -t $(sudo docker inspect -f '{{.State.Pid}}' $container) -n \
    iptables -t mangle -A POSTROUTING -p tcp -j TEE --gateway 10.7.1.32
done
```

これにより、モニターサーバー側ではプロミスキャスモードのインターフェースにて全トラフィックを受信・監視することが可能となる。

---

## 5. docker-compose運用のメリット

今回のシミュレーション環境のように複数のコンテナ（HMI, MES, PLC, Robot）を連携させるシステムを構築・運用する場合、純粋な `docker` コマンドを個別に使用するよりも `docker-compose` を用いるアプローチが圧倒的に優れている。

1. **起動順序の自動制御**
   `depends_on` を定義することで、PLCサーバが完全に立ち上がってからMESやHMIクライアントを起動する、といった依存関係の順序制御を自動で行うことができる。
2. **ネットワークと環境変数の統合管理**
   Macvlanネットワークの構築、IPアドレスの固定（`.40`〜`.43`）、およびGUI描画のためのデバイス共有（`/tmp/.X11-unix` など）をすべて `docker-compose.yml` という1つのコード（Infrastructure as Code）で正確に一元管理できる。
3. **ライフサイクルの統合とクリーンアップ**
   `up` と `down` だけで環境全体を丸ごと構築・破棄できる。ネットワーク上に古いエンドポイントが残って `failed to set up container networking` のようなエラーが発生した場合でも、エラー原因のコンテナを強制削除（例: `docker rm -f fa_sim_robot`）して再実行することで簡単に復旧可能である。

---

## 6. 補足: 仮想組み立て工場における通信のホワイトリスト

本仮想組み立て工場（OPC UAおよびEtherNet/IP環境）において、コンテナ間で許可される正規の通信経路（ホワイトリスト）を以下に定義する。

産業用プロトコル（OPC UA、EtherNet/IP）は、IPレベルの単純なパケット方向だけでなく、アプリケーション層での役割（クライアント/サーバ等）やコネクション確立の方向が重要となる。これを明確にするため、各ノードの役割およびL4プロトコル・ポート番号を含めて定義する。

### 正規通信ホワイトリスト定義

| 送信元 (Source IP) | Sourceの役割 | 送信先 (Destination IP) | Destinationの役割 | プロトコル | トランスポート / ポート | 備考（通信の方向・内容） |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `10.7.1.3` (Browser) | Web Client | `10.7.1.41` (HMI) | Web Server | HTTP | TCP / `8080` | ブラウザからの画面アクセス・操作要求 |
| `10.7.1.41` (HMI) | OPC UA Client | `10.7.1.40` (MES) | OPC UA Server | OPC UA | TCP / `4840` | HMIからMESへのデータ収集・監視 |
| `10.7.1.42` (PLC) | OPC UA Client | `10.7.1.40` (MES) | OPC UA Server | OPC UA | TCP / `4840` | PLCからMESへの製造パラメータ取得・ステータス同期 |
| `10.7.1.41` (HMI) | ENIP Originator | `10.7.1.42` (PLC) | ENIP Target | EtherNet/IP | TCP / `44818` | HMIからPLCへのExplicit Message (Read/Write) |
| `10.7.1.41` (HMI) | ENIP Originator | `10.7.1.43` (Robot) | ENIP Target | EtherNet/IP | TCP / `44818` | HMIからRobotへのエラー発生操作 (Explicit) |
| `10.7.1.42` (PLC) | ENIP Originator | `10.7.1.43` (Robot) | ENIP Target | EtherNet/IP | TCP / `44818` | PLCとRobot間のタグ読み書き通信（制御指示・ステータス監視） |

### 補足事項
* **IPレベルとアプリケーションレベルの分離**: IPパケットの方向（L3/L4）と、アプリケーションレイヤでの機能的役割（クライアント/サーバなど）を分離して定義することで、ネットワーク監視の基準を明確化する。
* **OPC UAの通信方向**: MESとPLC間の通信において、本環境ではPLC（制御系）がOPC UAクライアントとして、MES（上位系）のOPC UAサーバ（TCP `4840`）に対して接続要求を発行し、製造パラメータの取得やステータスの同期を行っている。
* **EtherNet/IPの特性**: 一般的な実機ではコネクション確立にTCP通信（ポート`44818`）、サイクリックなI/Oデータ通信にUDP通信（ポート`2222`）を使用するが、本仮想環境においてはすべてのタグ読み書きや制御通信をExplicit Message（TCPポート`44818`）として実装・定義している。
