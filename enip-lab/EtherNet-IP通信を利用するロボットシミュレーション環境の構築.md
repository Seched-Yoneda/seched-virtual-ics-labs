# EtherNet/IP通信を利用するロボットシミュレーション環境の構築 (Docker活用)

本ドキュメントは、オープンソースを用いて構築した「EtherNet/IP MES-PLC-ロボット連携シミュレーション」を、DockerおよびDocker Composeを活用してネットワーク設定やプロセスの起動・終了を自動化した新しい実行手順のまとめです。

## 1. 動作環境とアーキテクチャ概要

| 項目 | 内容 |
| --- | --- |
| **OS環境** | Ubuntu 24.04 Desktop (VirtualBox仮想マシン上) |
| **開発言語** | Python 3.12 |
| **PLC (サーバ)** | Dockerコンテナ化 (`enip_sim_plc`) / 10.7.1.37<br>ソフトウェアEtherNet/IP仮想アンプ/サーバ (`cpppo`) |
| **MES (クライアント)** | Dockerコンテナ化 (`enip_sim_mes`) / 10.7.1.38<br>EtherNet/IPプロトコル通信で指令を出すクライアント |
| **ロボット描画** | ホストOS上で実行 (`pybullet`)<br>実仮想物理シミュレーションと逆運動学計算・描画 |

**アーキテクチャ概要:**
ホストOS内にDockerの `macvlan` ネットワーク (10.7.1.x) を構築し、Virtual PLC（サーバ）と「指示を出すMESクライアント」をそれぞれ独立したコンテナとして立ち上げる。これに対してホストOSから「状態を監視して物理世界で動くRobotクライアント」が接続し、PLCのメモリ（タグ）を介して3者が連携する。

---

## 2. 【初回のみ】新規サーバーでの初期構築手順（ゼロから構築する場合）

Ubuntu 24.04サーバーに新規に環境を構築する場合は、シミュレーションを実行する前に以下の事前準備を行う。（すでに環境が構築済みの場合は「3. シミュレーションの実行手順」へ進む）

### 事前準備 1. 必須パッケージとDockerのインストール
Ubuntuの初期状態から、Pythonの仮想環境作成ツールやDocker関連をインストールします。
```bash
sudo apt update
sudo apt install -y python3-venv docker.io docker-compose
```

### 事前準備 2. ネットワークインターフェース名の確認と修正（重要）
環境によってmacvlanの親となるネットワークインターフェース名（例: `enp0s3`, `eth0`, `ens33` 等）が異なります。
1. `ip a` コマンドを実行して、現在メインで通信しているIPが割り当てられたインターフェース名を確認します。
2. もし `enp0s3` 以外だった場合は、あらかじめ以下の2つのファイルを開き、該当箇所を実際のインターフェース名に書き換えてください。
   - `setup_network.sh` の `PARENT_INTERFACE="enp0s3"`
   - `docker-compose.yml` の `parent: enp0s3`

### 事前準備 3. ホスト用Robotシミュレータ(venv)の環境構築
ホストOS側でロボットを描画するため、Pythonの仮想環境と必要なパッケージを用意します。
```bash
cd /home/kali/localwork/enip_sim
python3 -m venv venv
source venv/bin/activate
pip install pybullet cpppo
```
この準備が完了すれば、以降の「3. シミュレーションの実行手順」へスムーズに進めるようになります。

---

## 3. シミュレーションの実行手順（日々の起動・終了）
ロボットシミュレータはホストOS上で実行するため、FADockerHost上で端末を開き、以下の手順を実行します。

### Step 1. ホスト側ネットワークの準備
コンテナ群が所属するmacvlanネットワークに対し、ホストOSから相互通信できるようにルーティングブリッジを作成します。
※OS起動後、シミュレーションを実行する前に最初に1回実行する必要があります。
```bash
cd /home/kali/localwork/enip_sim
./setup_network.sh
```

### Step 2. コンテナ（PLCサーバ・MESクライアント）のビルドと起動
Docker Composeを使って、バックグラウンド環境でイメージの自動ビルドおよびPLCサーバとMESクライアントのコンテナ起動を行います。コマンド一つで起動順序を含めて立ち上がります。
```bash
sudo docker-compose up -d --build
```
Dockerイメージの元となるファイルに 一切変更がない場合は `--build` は不要です。
```bash
sudo docker-compose up -d
```

※起動状況は `sudo docker-compose ps` で確認できます。MESコンテナはPLCコンテナの起動完了を待ってから連動して立ち上がります。

### Step 3. ロボットシミュレータの実行
ホスト上でロボットシミュレータを起動し、対象となるPLCのIP（`10.7.1.37`）を指定して監視させます。
```bash
cd /home/kali/localwork/enip_sim
source venv/bin/activate
PLC_IP=10.7.1.37 python robot_sim.py
```
起動完了後、MESが送信したPick（ピック）指令を検知し、物理演算処理が開始されます。
再度、PLC_IP=10.7.1.37 python robot_sim.pyを実行する場合は、
mesコンテナが停止していますので、
```bash
sudo docker-compose start mes
```
を実行してからPLC_IP=10.7.1.37 python robot_sim.pyを実行する。



### Step 4. シミュレーションの終了
終了したら、バックグラウンドで動いているDockerコンテナ群をまとめて停止・削除します。
```bash
sudo docker-compose down
```

---

## 4. モニターサーバー（IDS等）での通信パケットキャプチャ設定

プラントのサイバーセキュリティ演習において、ネットワークの通信を監視・分析するためのモニターサーバー（IDS: 侵入検知システムなど・例: `10.7.1.32`）を設置することが一般的です。

しかし、今回の構成では「DockerのMacvlanネットワーク」を利用しており、同一ホスト内で稼働するコンテナ同士（`enip_sim_plc` と `enip_sim_mes`）の通信は、物理的なネットワークインターフェース（例: `enp0s3`）の外に送出されず、Linuxカーネル内部の仮想Macvlanスイッチ内で直接折り返されて完結します。

このため、**外部のデバイスや別仮想マシンにあるモニターサーバー側には一切パケットが流れない**という事象が発生し、そのままではモニターサーバーのインターフェースをプロミスキャスモードにしてもEtherNet/IPのパケットをキャプチャできません。

これを解決し、**プラント本番環境の「L2スイッチのミラーポート（SPANポート）」をソフトウェア的に完全再現する**ため、Linuxカーネル標準の機能（`iptables TEE` ターゲットによるパケット複製）を利用します。

### 設定手順（iptables TEEによるパケット複製）

ここでは「通信の的」となっている `enip_sim_plc` コンテナのネットワーク名前空間に入り込み、EtherNet/IP通信パケット（TCP 44818番ポート）の完全なコピーをモニターサーバー（`10.7.1.32`）へ複製・送信するルールを追加します。これにより、MESからの指令や、ホスト上のロボットシミュレータからのパケットを全て捕捉できます。

**1. Dockerホスト側でポートミラーリングルールを追加する**
Dockerホストマシン（Kali Linux）上で以下のコマンドを実行し、PLCコンテナの出入口にルールを適用します。

```bash
# PLCが受信するリクエスト（宛先ポート44818）のコピーをモニターサーバーへ転送
sudo nsenter -t $(sudo docker inspect -f '{{.State.Pid}}' enip_sim_plc) -n \
  iptables -t mangle -A PREROUTING -p tcp --dport 44818 -j TEE --gateway 10.7.1.32

# PLCが送信するレスポンス（送信元ポート44818）のコピーをモニターサーバーへ転送
sudo nsenter -t $(sudo docker inspect -f '{{.State.Pid}}' enip_sim_plc) -n \
  iptables -t mangle -A POSTROUTING -p tcp --sport 44818 -j TEE --gateway 10.7.1.32
```

**2. モニターサーバー側でのキャプチャ確認**
モニターサーバー（`10.7.1.32`）の端末で、`tcpdump` などを実行して通信が取得できることを確認します。
※宛先IPが自分宛てでなくても、対象のMACアドレス宛てに送信されるためキャプチャツール上では見ることができます。

```bash
# モニターサーバー側のインターフェース（例：enp0s3）上でキャプチャを実行
sudo tcpdump -i enp0s3 -n port 44818
```

この設定により、パケットダンプや侵入検知システム（Snort、Suricata等）で、物理的なミラーポートを介しているのと全く同じように生トラフィックを監視させることが可能になります。

> [!IMPORTANT]
> **設定の揮発について**
> この `iptables` によるミラーリング機能はメモリ上の設定です。そのため、**OS（ホストマシン）の再起動や、コンテナの再起動・再作成（`docker-compose down` / `up` 等）を行うたびに設定が消去されます。**
> 通信を再度キャプチャしたい場合は、コンテナが起動した後に毎回必ず同じ手順（上記コマンドの実行）を実施する必要があります。

---

## 補足
### 0. PLC,MESへの内部ネットワークの他のゲストOSからのping

`sudo ip link set enp0s3 promisc on`
を実行しenp0s3プロミスミスキャスモードにする必要がある。

親インターフェースであるenp0s3が、その上に構築されたmacvlanエンドポイント（10.7.1.37や10.7.1.38）宛てのパケットを入り口で弾かずに受信・転送できるようにするため。

10.7.1.37（PLC）や10.7.1.38（MES）は、enp0s3を親（parent）として作られたmacvlanネットワーク上のコンテナであり、ホストOSのenp0s3とはそれぞれ別々の仮想MACアドレスを持っている。

通常、ネットワークインターフェース（enp0s3）は自身のMACアドレス宛てのパケットしか受け取らない。そのため、外部の他のゲストOSから10.7.1.37や10.7.1.38へping等の通信を行っても、パケットの宛先MACアドレスがenp0s3自身とは異なるため、破棄されてしまう。

これを防ぐために、enp0s3をプロミスキャスモードにしてすべての指定外パケットを受信可能な状態にすることで、macvlan上のコンテナへ正常にパケットを橋渡しできるようにしている。

### 1. Docker Composeによるコンテナ・ネットワーク管理の内部仕様

`docker-compose.yml` はシステム全体の中核となる「仮想ネットワーク環境」の構築と「各ノード（コンテナ）プロセス」を統合管理しています。

*   **ネットワーク定義 (`macvlan`)**:
    *   ホストOS（`enp0s3`など）を親インターフェースとして、`10.7.1.0/24` のサブネットを持つ `macvlan` ネットワーク (`pub_net`) を構築します。
    *   これにより、各コンテナがあたかも物理ネットワーク上の独立した機器のように直接IPアドレス（`10.7.1.x`）を割り当てられて通信可能になります。
*   **PLCコンテナ (`enip_sim_plc`)**:
    *   `Dockerfile.plc` を用いて、Pythonと `cpppo` ライブラリを含むバックグラウンド実行用イメージを自動ビルドします。
    *   コンテナ起動時に固定IP `10.7.1.37` を割り当て、常にネットワーク上でEtherNet/IPのTCP/44818ポートでリクエストを待ち受ける状態を維持します。
*   **MESコンテナ (`enip_sim_mes`)**:
    *   `Dockerfile.mes` を用いて、`mes_client.py` 実行環境のイメージを自動ビルドします。
    *   固定IP `10.7.1.38` を割り当てます。また、`depends_on` 設定により必ずPLCコンテナが起動した後に連動して立ち上がる順序制御を行っています。
    *   環境変数 `PLC_IP=10.7.1.37` を内部に注入することで、スクリプトの接続先ホスト指定を動的に向けています。

---

### 2. `docker-compose` と純粋な `docker` コマンドの運用比較

今回のシミュレーション環境のように「PLCサーバ」と「MESクライアント」という**複数のコンテナを連携させるシステム**を構築・運用する場合、純粋な `docker` コマンドを個別に叩くよりも `docker-compose` を用いる方が圧倒的に優れています。以下にビルド・起動・終了の手間の違いを比較します。

#### 【比較表】ビルド・起動・終了のコマンド

| 運用フェーズ | 純粋な `docker` コマンドによる手動運用 (コンテナ毎に実行) | `docker-compose` による一括運用 (今回) |
| :--- | :--- | :--- |
| **事前準備 (ネットワーク設定)** | `docker network create -d macvlan --subnet=10.7.1.0/24 -o parent=enp0s3 pub_net` | `docker-compose.yml` に定義済みのため不要 |
| **ビルド (イメージ作成)** | `docker build -t enip_sim_plc -f Dockerfile.plc .`<br>`docker build -t enip_sim_mes -f Dockerfile.mes .` | **不要** (ymlで設定済み)<br>`docker-compose up -d --build` の一撃で自動ビルド |
| **起動 (実行)** | `docker run -d --name enip_sim_plc --network pub_net --ip 10.7.1.37 enip_sim_plc`<br>`docker run -d --name enip_sim_mes --network pub_net --ip 10.7.1.38 -e PLC_IP=10.7.1.37 enip_sim_mes` | **コマンド1つ**<br>`docker-compose up -d` |
| **終了 (停止と不要物削除)** | `docker stop enip_sim_mes enip_sim_plc`<br>`docker rm enip_sim_mes enip_sim_plc` | **コマンド1つ**<br>`docker-compose down` |

#### システム構築において `docker-compose` の方が適している理由

1. **起動順序の自動制御ができる**
   MESクライアントは、PLCサーバが起動していなければ接続先が見つからずエラーになります。純粋なDockerコマンドの場合、人間が順番に起動するか、複雑なシェルスクリプト（以前の `start.sh` のようなもの）を自作する必要があります。Composeなら `depends_on: - plc` を書くだけでPLC→MESの順番を自動で担保します。
2. **ネットワークと環境変数の設定ミスを防ぐ**
   複数のコンテナが同じネットワーク(`pub_net`)に所属し、正しい環境変数(`PLC_IP=10.7.1.37`など)を渡し合う必要があります。これらを全て `.yml` ファイルとしてコード化（Infrastructure as Code）できるため、手打ちによるタイプミスや設定の引き継ぎ漏れが起きません。
3. **ライフサイクルの統合管理**
   「一括でビルド・起動し、一括で綺麗に落とす」という一連の動作が `up` と `down` だけで完結します。純粋な `docker` コマンドで運用すると、停止後に不要になったコンテナプロセスが残りやすく、次回起動時のエラー（ポートの競合や名前の重複など）を引き起こすリスク（先ほど発生したような事例）を最小限に抑えられます。

---

### 3. プロジェクトのファイル構成

新しいUbuntu環境やGitHub上で本システムを再現するために必要な、完全なファイル群は以下の通りです。

* **[インフラ・ネットワーク定義系]**
  * `docker-compose.yml`
  * `setup_network.sh`
* **[Dockerコンテナ（PLC / MES）系]**
  * `Dockerfile.plc`
  * `Dockerfile.mes`
  * `mes_client.py` (MESコンテナ内で使われる)
* **[ホストOS（Robot）系]**
  * `robot_sim.py` (ホストOS上で直接動く)
  * `requirements.txt` (ホストOSのvenvにインストールする pybullet, cpppo などを記載)

### 4. 3Dモデルデータについて

`robot_sim.py` の中で読み込んでいるロボットアーム（KUKA iiwa）や積み木、床などの3Dモデルデータは全て、`requirements.txt` でインストールする `pybullet` というパッケージ内に最初から内蔵されている標準データを利用しています。
そのため、別途3DモデルのファイルをGitHubに上げる必要もなく、このコード群だけで完全に自己完結して動く非常に綺麗なリポジトリ構成と言えます。
