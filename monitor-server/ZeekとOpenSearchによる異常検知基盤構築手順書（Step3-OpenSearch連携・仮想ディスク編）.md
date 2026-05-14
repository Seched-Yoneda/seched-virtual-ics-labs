# Zeek と OpenSearch による 異常検知基盤構築手順書(Step3:OpenSearch連携・仮想ディスク編)

## 1. Zeekのログ出力をJSON形式に変更およびプラグインの有効化
Zeekの初期設定であるTSV（タブ区切り）形式のログをJSON形式に変更し、さらにインストール済みの拡張プラグイン（`icsnpp-enip`など）を確実に有効化するため、`local.zeek` の設定ファイルに対して変更を行った。

### local.zeek への設定追加・変更
エディタ（nanoやviなど）で `sudo vi /opt/zeek/share/zeek/site/local.zeek` を開き、以下の２点の状態を確認・変更する。

1. **プラグインの有効化:**
   ファイル末尾付近にある `# @load packages` という行を探し、先頭の `#` を削除（コメントアウトを解除）して `@load packages` にする。これにより `zkg` でインストールした解析プラグインが起動時に読み込まれるようになる。

2. **JSON形式の追記:**
0   ファイルの最も最後の行に `@load policy/tuning/json-logs.zeek` を追記する。 (※追記後、必ずファイル末尾に改行を1つ入れておくこと)
      
```bash
# （参考）JSONログ出力設定のみをコマンドラインから追記する場合
echo '@load policy/tuning/json-logs.zeek' | sudo tee -a /opt/zeek/share/zeek/site/local.zeek
```

※補足：OpenSearchを用いた24時間連続での異常検知を実現するため、本手順よりZeekの運用を「コマンドラインからの手動実行」から、「`zeekctl` と設定ファイル（`node.cfg`）を用いたバックグラウンドでの自動実行機能（常駐・ログ自動ローテーション）」へと切り替える。次節でそのための具体的な設定変更を行う。

## 2. ライブキャプチャ運用のためのZeekインターフェース設定
監視するインターフェース(今回は、enp0s3)を node.cfgのinteraceに指定する。

### 設定ファイル（node.cfg）の書き換え
Zeekのノード設定ファイルを開き、監視対象のインターフェースを指定している箇所を修正する。

- 対象ファイル： `/opt/zeek/etc/node.cfg`
- 変更箇所：
```ini
[zeek]
type=standalone
host=localhost
interface=enp0s3 #  enp0s3 を指定する
```

### Zeekの再設定および起動（deploy）
設定の変更を反映させるため、Zeekの設定反映・起動コマンド（`zeekctl deploy`）をroot権限で実行した。

```bash
sudo /opt/zeek/bin/zeekctl deploy
```

これにより、`enp0s3` を流れるENIPトラフィックがあれば、リアルタイムでJSONログが出力され、それがFilebeat経由で直ちにOpenSearch Dashboardsに転送される状態が完成した。

## 3. Docker および Docker Compose のインストール
Ubuntu環境の初期状態ではDockerがインストールされていなかったため、パッケージリストの更新とDocker関連ツールのインストールを実行した。

```bash
# パッケージリストの更新とDockerパッケージのインストール
sudo apt update
sudo apt install -y docker.io docker-compose
```

## 4. OpenSearch用ディレクトリと設定ファイルの作成
Docker Composeで起動するOpenSearchスタックの設定ファイルを配置するためのディレクトリを作成し、2つの設定ファイルを配置した。

> [!IMPORTANT]
> **OpenSearchのバージョン指定について**
> 本構成では、Zeek生ログの転送を担う `Filebeat 7.x (OSS版)` との完全な互換性を確保するため、あえて最新版（2.x系等）ではなく、実績があり極めて安定している1.x系の最終安定版である **`OpenSearch 1.3.14`** を指名して採用している。2.0以降では内部仕様（`_type` の廃止など）が変更されており連携エラーが発生するため、アップデート等は行わず必ずこのバージョンを固定して運用すること。

> [!NOTE]
> **【補足】なぜOpenSearchに「Filebeat (OSS版)」を組み合わせているのか？**
> 本アーキテクチャで「Elastic社製のツールであるFilebeat」と「OpenSearch」という別プロジェクトの製品を組み合わせている背景には、オープンソース界隈の歴史的な事情がある。
> もともとOpenSearchは、Elasticsearch（バージョン7.10）のソースコードをベースに派生（フォーク）して作られた製品である。しかし分裂後、本家Elastic社は自社の最新版ツール（Filebeat 8.x等）に対して「接続先がOpenSearchだと判明した瞬間に通信をブロックする」という強い制限を追加した。また、商標やライセンスの観点から、OpenSearch側がFilebeatを自社プロジェクトの一部として公式配布することもできない。
> そのため、通信ブロック制限が追加される前の**「純粋なオープンソース版の古いFilebeat（7.x OSS版）」**を、OpenSearchとは独立した別コンポーネントとしてあえて組み合わせることが、現在のOpenSearchコミュニティにおける最も賢明で安定したベストプラクティスとなっている。また、zeekをopensearchで扱い際は、10年規模のノウハウがされているfilebeat(OSS版)を使う方がAntigravity等AIエージェントのトラブルシューティングの精度が高い。

```bash
# 作業ディレクトリの作成
mkdir -p /home/kali/localwork/opensearch_stack
cd /home/kali/localwork/opensearch_stack
```
以下の2つのファイルを `/home/kali/localwork/opensearch_stack` ディレクトリ下に作成した。

### ① docker-compose.yml の記載事項
本ファイルにおいては、以下の設定を定義した。
- `zeekctl` でのライブ運用への移行に伴い、Filebeatが監視する対象を「手動実行時のログ出力先」から、公式の「`/opt/zeek` 配下」へと変更した。
- そのため、Filebeatコンテナ（隔離環境）が本体OSのログを安全に読み込めるよう、ホストの実ディレクトリ `/opt/zeek` を read-only（読み取り専用: `ro`）でマウントするよう記載した。filebeatは`/opt/zeek/spool/zeek/*.log` などを監視する。
- **ネットワーク構築（`networks: elk: driver: bridge`）について**：
  実際のLAN（DHCPサーバ等）のIPアドレスを消費・干渉させないよう、Docker内部に完全に独立した専用の仮想ネットワークを構築している。各コンテナはこの内部網でのみセキュアに連携機能を提供する。
- **ポートフォワーディング設定（`ports:`）の有無について**：
  OpenSearch Dashboardsなど外部（ブラウザ等）からのアクセスが必要な機能にはポートフォワーディングを設定している。一方、Filebeatは本体OSのログを読み込みOpenSearchへデータを送信（Push）するだけの役割であり、外部からのアクセス要求（Web UI等）が存在しない。そのため、あえてポートを解放せず、内部ネットワーク上だけで安全に動作するように設計している。

```yaml
version: '3.7'

services:
  opensearch:
    image: opensearchproject/opensearch:1.3.14
    container_name: opensearch
    environment:
      - cluster.name=opensearch-cluster
      - node.name=opensearch-node1
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g
      - DISABLE_INSTALL_DEMO_CONFIG=true
      - plugins.security.disabled=true
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    ports:
      - "9200:9200"
      - "9600:9600"
    volumes:
      - opensearch_data:/usr/share/opensearch/data
    networks:
      - opensearch-net

  opensearch-dashboards:
    image: opensearchproject/opensearch-dashboards:1.3.14
    container_name: opensearch-dashboards
    ports:
      - "5601:5601"
    environment:
      - OPENSEARCH_HOSTS=["http://opensearch:9200"]
      - DISABLE_SECURITY_DASHBOARDS_PLUGIN=true
    depends_on:
      - opensearch
    networks:
      - opensearch-net

  filebeat:
    image: docker.elastic.co/beats/filebeat-oss:7.12.1
    container_name: filebeat-opensearch
    user: root
    volumes:
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
      - /opt/zeek:/opt/zeek:ro
    depends_on:
      - opensearch
    networks:
      - opensearch-net

networks:
  opensearch-net:
    driver: bridge

volumes:
  opensearch_data:
```

### ② filebeat.yml の作成

```yaml
filebeat.inputs:
- type: log
  id: zeek-logs
  enabled: true
  paths:
    - /opt/zeek/spool/zeek/*.log
    - /opt/zeek/logs/*/*.log
  # JSON形式のログをパースする設定
  json.keys_under_root: true
  json.add_error_key: true
  json.overwrite_keys: true

setup.template.enabled: false
setup.ilm.enabled: false

output.elasticsearch:
  # 送信先をOpenSearchコンテナに指定（OSS版なのでopensearch outputモジュールで通信可能）
  hosts: ["opensearch:9200"]
  index: "filebeat-7.12.1-%{+yyyy.MM.dd}"
  # ※今回は認証（plugins.security.disabled=true）をオフにしているため、username/passwordは不要です

processors:
  - rename:
      fields:
        - from: "service"
          to: "network.protocol"
        - from: "source"
          to: "zeek.source"
      ignore_missing: true
      fail_on_error: false
  - add_host_metadata: ~
  - add_cloud_metadata: ~
  - add_docker_metadata: ~
  - add_kubernetes_metadata: ~
```

### ③ filebeat.yml の権限変更（必須）
Filebeatはコンテナ仕様上、設定ファイル（`filebeat.yml`）の所有権が `root` 以外になっているとセキュリティエラーで強制終了する。そのため、コンテナを起動する前にホスト側にある同ファイルの所有者を一時的に `root` に変更しておく必要がある。

```bash
# 所有者をrootに変更する
sudo chown root:root filebeat.yml
```

## 5. Dockerコンテナ (OpenSearchスタック) の起動
作成した `docker-compose.yml` を使用して、OpenSearch、OpenSearch Dashboards、Filebeatのすべてを含めたコンテナ群をバックグラウンドで起動（イメージのダウンロードを含む）した。

```bash
# Dockerコンテナの起動
./start_elk.sh
```
※補足：この `start_elk.sh` は、VMのディスク枯渇を防ぐため「事前にログ用の外部ストレージ（HDD）が正常に接続・マウントされているか」を確認したうえで、実質的に `sudo docker-compose up -d` を実行する安全機能付きの起動スクリプトである。

## 6. 今後の運用・メンテナンス手順
本環境における設定変更および再起動は、以下の手順にて実施する。ツールごとに管理アーキテクチャが異なるため、それぞれ専用のコマンドを用いる。

### 6.1. Zeekの設定変更および再起動
設定ファイル（`local.zeek`, `node.cfg` など）の修正を反映し、安全に再起動を行う場合は、専用の管理コマンドを使用する。

```bash
# Zeekの設定構文チェック、古いプロセスの終了、新設定での再起動を自動実施
sudo /opt/zeek/bin/zeekctl deploy
```
※補足：単なる `restart` ではなく、常に `deploy` を用いるのが定石である。これにより設定の検査が事前に行われるため、安全な再稼働が担保される。

### 6.2. OpenSearchスタック（Dockerコンテナ）の設定および再起動
OpenSearch群については、Docker Composeを利用して一括あるいは個別の起動・再起動や設定反映を行う。

**全体の再構築と設定の反映（`docker-compose.yml` や `filebeat.yml` を反映する場合）**

> [!WARNING]
> `filebeat.yml` を編集した場合は、コンテナ起動前に必ず **`sudo chown root:root filebeat.yml`** を実行すること。編集方法（ファイルの再作成や上書き等）によっては所有者が `kali` に戻ってしまい、Filebeatがセキュリティエラーで起動しなくなるためである。

```bash
cd /home/kali/localwork/opensearch_stack

# 既存のコンテナ群を一度完全に停止・削除し、再度クリーンな状態で起動する
sudo docker-compose down

# filebeat.ymlの所有者をrootへ確実に戻す（編集した場合の必須処理）
sudo chown root:root filebeat.yml

# 再起動
sudo docker-compose up -d
```

**特定のコンテナの単体再起動（設定変更はないが単にアプリケーションをリスタートしたい場合）**
```bash
cd /home/kali/localwork/opensearch_stack

# 例：Filebeatコンテナのみ再起動する
sudo docker-compose restart filebeat
```


### 6.3. 運用上のポイント：ディスク容量管理とログの保持期間
本基盤では、ネットワークパケットのメタデータ（Zeekログ）と、それを検索・可視化するためのデータベース（OpenSearch）が稼働する。両者で古いデータの扱いが異なる点に注意が必要である。

- **Zeek (zeekctl):**
  設定（`LogExpireInterval`）に基づき、古いログを自動で `.gz` 形式に圧縮し、長期間アーカイブとしてディスク上に保持し続ける。
- **OpenSearch (ILM):**
  高速な検索を提供するためディスク容量を多く消費する。設定期間（例：90日）を超過したデータ（インデックス）は、ディスクフルによるシステムクラッシュを防ぐために**ディスク上から完全に自動削除（破棄）**される。

### 6.4. 運用上のポイント：OSアップデート時の影響とバージョン管理
本基盤を構成する「Zeek」と「OpenSearchスタック」は、パッケージ管理のアーキテクチャが異なるため、OSアップデート（`apt upgrade`）時の影響も異なります。

- **OpenSearchスタック（OpenSearch, OpenSearch Dashboards, Filebeat）:**
  これらはDockerコンテナとして稼働しており、`docker-compose.yml` 内でバージョン（例: `8.10.2`）がハードコード（固定指定）されています。そのため、OS上でどれだけ `apt upgrade` を行っても、意図せずバージョンが上がることはなく安全です。**`apt-mark hold` 等によるアップデート除外設定は不要**（そもそもaptの管理外）です。

- **Zeek:**
  Zeekは公式リポジトリから `apt` 経由で直接OSにインストールされています。そのため、OSのアップデートに巻き込まれてバージョンが上がると、独自コンパイルしたプラグインが破損するリスクがあります。（※この破損を防ぐための `apt-mark hold` の手順は、Zeek構築編である Step1 および Step2 に記載されています）


## 7. OpenSearch Dashboardsでの初期設定と通信（ENIP）確認手順
ブラウザでOpenSearch Dashboards（例： `http://10.7.1.32:5601`）へアクセスした初期画面から、Zeekが解析したENIPパケットを一覧表示するまでの手順を以下に示す。

### 7.1. Data View の作成（初回のみ）
OpenSearch DashboardsにFilebeatからのデータを認識させるための設定を行う。
1. OpenSearch Dashboardsの初期画面（Welcome to Elastic）の中央にある **「Explore on my own」** をクリックする。
2. 画面左上のハンバーガーメニュー（ ≡ アイコン）をクリックしてメニューを開く。
3. 下部 `Management` カテゴリ内の **「Stack Management」** をクリックする。
4. 左側のサイドバーから、`OpenSearch Dashboards` カテゴリ内にある **「Data Views」** をクリックする。
5. 右上の青いボタン **「Create data view」** をクリックする。
6. 設定画面で以下の項目を入力・選択する：
   - **Name**: `filebeat-*` と入力。
   - **Index pattern**: `filebeat-*` と入力。
   - **Timestamp field**: プルダウンメニューから `@timestamp` を選択。
7. 右下の **「Save data view to OpenSearch Dashboards」** をクリックして保存する。

### 7.2. ログ一覧（Discover）でのENIPトラフィック確認
作成したData Viewを用いて、流れてきたパケットをリアルタイムに確認する。
1. 再度、画面左上のメニュー（ ≡ アイコン）を開く。
2. 上部 `Analytics` カテゴリ内にある **「Discover」** をクリックする。
3. 画面左上のプルダウンで `filebeat-*` が選ばれていることを確認する。
4. **ENIPログだけを抽出する（フィルタリング）**
   - 画面左側のサイドバー最上部（`Selected fields` の上）にある「🔍 Search field names」という検索フィールドに **`log.file.path`** と入力する。
   - すぐ下に表示された `log.file.path` をクリックすると、「よく出現するログファイル名」がリストで表示される。
   - その中にある **`/opt/zeek/spool/zeek/enip.log`** の横に表示される **「＋」ボタン（Filter for value）** をクリックする。
   - これにより、画面上のすべてのデータが「EtherNet/IPのパケット情報（enip.log）」のみに完全に絞り込まれる。
5. **パケットの中身（送信元・宛先IP等）を確認する**
   - 画面下部のログ一覧に並んでいるパケット（各行）の一番左にある、**「斜めの双方向矢印」（Toggle dialog with details）アイコン** をクリックする。
   - 画面右側に **「Expanded document」** という詳細パネルが開く。
   - パネル内の各項目は **アルファベット順（A〜Z）** に並んでいる。下へスクロールしていくことで、Zeekが解析した以下の具体的な通信情報が確認できる。
     - **`destination.h`** ： 宛先IPアドレス
     - **`destination_p`** ： 宛先ポート番号
     - **`enip_command`** ： ENIPコマンド名（例：`Send RR Data`）
     - **`id.orig_h`** （または Filebeatにより変換された `source.h` など）： 送信元IPアドレス（A〜Z順でSやIは下の方にあるため、DやEの項目よりもさらに下へスクロールすると出現する）


※【注】 Data View設定時の `filebeat-*` に含まれるアスタリスク（`*`）の意味について：
Filebeatは、裏側でログデータを「日別」や「バージョン別」（例：`filebeat-8.10.2-2026.04.14`）に自動で細分化してOpenSearchに保存している。Data Viewで `filebeat-*` とワイルドカードを用いることで、「過去から未来にわたる全ての日付のログデータを横断的に合体させて表示させる」という重要な働きをしている。

※【注】 Discover画面の見方と、一覧表を見やすく整理するコツ（初心者向けガイド）：
- **上部の棒グラフ（ヒストグラム）**：横軸を時間とし、「いつ・何件の通信や処理が発生したか」を示す。例えば「822 hits」とあれば、指定期間内にシステムで822件の対象パケットが観測されたことを意味する。
- **下部の一覧リスト（Documents）**：取得したログの「生データ」。初期状態ではFilebeatという運び屋自身のシステム情報などが見えており扱いづらい。
- **オリジナルの通信一覧表（ダッシュボード）を作る方法**：画面左端・最上部の検索フィールド（🔍 Search field names）に、表に出したい項目（例：`destination.h`、`id.orig_h`、`enip_command` 等）を入力する。該当項目の右に現れる「＋」（Toggle column in table）を押して追加していくと、画面下のリストがIPアドレスやコマンドが並んだ綺麗な「表計算ソフトのような見た目」になり、通信状況が一目で判別できるようになる。

---

## 8. OpenSearchデータの外部ストレージ（USB HDD）移行（強く推奨）

本手順書（Chapter 1〜7）では、動作確認を優先するため、一時的にゲストOS内の仮想ローカルディスクにOpenSearchのデータを保存する設定となっている。
しかし、仮想環境（VM）はローカルディスクの容量が限られており、長期間ネットワークログを蓄積し続けると数日〜数週間でディスクが枯渇し、システムがクラッシュする危険がある。

そのため、正常な動作が確認できた後は、**必ず別紙の手順に従い、大容量のUSB接続の外付けHDDへOpenSearchのデータを移行し、データ保存先を変更すること。**

詳細な移行手順については、以下のドキュメントを参照すること。
👉 **[Zeek と OpenSearch による 異常検知基盤構築手順書(Step4:OpenSearch連携・外付けHDD編).md](./Zeek と OpenSearch による 異常検知基盤構築手順書(Step4:OpenSearch連携・外付けHDD編).md)**

---

## 補足: 異常検知までのプロセス（ロードマップ）
本基盤構築後、実際にEtherNet/IPのトラフィックから異常検知・可視化をテストするまでの大まかなロードマップと、必要なモジュール操作（設定追加・再起動等）の有無を以下にまとめる。

### Phase 1: EtherNet/IPのトラフィックをZeekに流し込む
- **対象モジュール:** ネットワーク環境（ホストOS、シミュレータ等のソフトウェア）
- **実施内容:** `enp0s3` 上に実際のENIPパケットを発生させる（`tcpreplay` によるPCAP再生や、各種通信スクリプトの実行）。
- **設定・再起動:** **不要**。Zeekはバックグラウンドで `enp0s3` を監視状態であるため、通信が発生した瞬間に自動でログを記録する。

### Phase 2: OpenSearch Dashboardsで可視化の状態を見る
- **対象モジュール:** OpenSearch Dashboards（ブラウザからアクセスするWeb UI）
- **実施内容:** ブラウザからOpenSearch Dashboardsにアクセスし、「Data View」で `filebeat-*` を作成してログを認識させる。その後、送信元IPやENIPコマンドの種類などをグラフ化して可視化ダッシュボードを作る。
- **設定・再起動:** **不要**。すべてコンテナを稼働させたまま、ブラウザ上のGUI操作で完結する。

### Phase 3: 異常検知のためのルール追加（学習）
- **対象モジュール:** Zeek（シグネチャ・スクリプト） ※本手順内で最も設定変更と再起動が伴う工程
- **実施内容:** 通常の通信とは異なる「怪しいENIP通信（特定IP以外からのアクセス、危険なリセットコマンドの検知等）」を定義する。
- **設定追加:** 独自検知用のスクリプト（`.zeek` ファイル）を作成し、`/opt/zeek/share/zeek/site/local.zeek` に `@load` で読み込み設定を追記する。
- **再起動:** **必要**。`sudo /opt/zeek/bin/zeekctl deploy` を実行し、Zeekに新しい検知ルールを学ばせる。
- *(※OpenSearch Dashboards側の機能を用いたしきい値アラート等を作成する場合は、再起動不要でGUI完結の対応も可能)*

### Phase 4: 攻撃を試行し、検知されるか確認する
- **対象モジュール:** 攻撃用ホスト、または評価用スクリプト環境
- **実施内容:** NmapのENIPスキャンや専用スクリプトを用いて、Phase 3で定義した「不正なパケット」をあえて送信する。
- **設定・再起動:** **不要**。攻撃実施中は設定を変えず、リアルタイムでOpenSearch Dashboards上に「異常」としてログやアラートが表示されるかを確認する。結果に応じてPhase 3に戻り、ルールを微調整する。

---

## 補足2: Dashboardでのネットワーク相関図（ヒートマップ）作成手順
OpenSearch Dashboards無料版の基本機能を用いて、「どのIPとどのIPがどれくらい通信しているか」を視覚的に把握できるヒートマップの作成手順を以下に示す。

1. **Dashboardエディタの起動**
   - OpenSearch Dashboards画面左上のメニューから `Analytics` ＞ **「Dashboard」** を選択する。
   - 中央の青いボタン **「Create a dashboard」** をクリックし、続けて **「Create visualization」** をクリックする。
2. **グラフの種類の変更**
   - 画面中央上部にあるグラフ選択プルダウン（初期状態は棒グラフ）を開き、一覧から **「Heatmap（ヒートマップ）」** を選択する。
3. **データソースとフィルターの設定**
   - 画面左上のデータソースが `filebeat-*` になっていることを確認する。
   - もしENIP通信のみを描画したい場合は、上部検索バーに `log.file.path : *enip*` と入力する。
4. **横軸・縦軸（送信元IP・宛先IP）のマッピング**
   - 画面左端の検索窓（🔍 Search field names）に **`destination.h`** （宛先IP）と入力する。
   - リストアップされた文字列をマウスで掴んだまま（ドラッグ状態）、画面右側のコントロールパネルにある **「Vertical axis（縦軸）」** のグレー枠の中まで運び、指を離す（ドロップ）。
   - 同じく検索窓に **`id.orig_h`**（または送信元IPを表す `source.h` 等）と入力し、今度は **「Horizontal axis（横軸）」** の枠へドラッグ＆ドロップする。
5. **ヒートマップの色の濃さ（通信量）を設定する**
   - このままだと「箱」ができるだけで色が塗られないため、左側の検索窓の右端のバツ印（✖）をクリックして検索をクリアする。
   - リストの一番上に現れる緑色アイコンの **`# Records`** を掴む。
   - 画面右側の一番下、赤文字で「Requires field」とエラーが出ている **「Cell value」** の枠へドラッグ＆ドロップする。
6. **完成と保存**
   - これで通信量に応じたクロス集計マップが完成する。右上の青い **「Save and return」** ボタンを押して保存することで、いつでも自分専用の監視ダッシュボードとして運用できる。

---

## 補足2.5: Vegaを用いたネットワーク相関図（クモの巣グラフ）の作成
IPアドレス同士を線で結ぶグラフィカルな相関図を作成したい場合は、別紙の **[ZeekとOpenSearchによる可視化手順書.md](./ZeekとOpenSearchによる可視化手順書.md)** を参照してVegaグラフを追加してください。

---

## 補足3: トラブルシューティング（OpenSearch Dashboardsの表示がおかしい時）
OpenSearch Dashboardsの画面が真っ白なままデータが来ない、またはDashboardの表示がおかしい場合は、エラーの原因が「Zeek側（パケットを拾えていない）」か「OpenSearch側（ログを運べていない/表示できていない）」かを素早く切り分けるため、以下の確認を行う。

1. **Zeek側のステータスとログ出力確認**
   - コマンド: `sudo /opt/zeek/bin/zeekctl status`
   - 確認ポイント: `Status` が `running` になっているか確認する。
   - ログ出力確認: `tail -n 10 /opt/zeek/spool/zeek/enip.log` などを実行し、最新時刻のJSON形式ログが吐き出され続けているか（Zeekがパケットを正しく拾って出力までできているか）を確認する。
2. **OpenSearch・Filebeat側のコンテナ状態確認**
   - コマンド: `sudo docker ps` または OpenSearchの `docker-compose.yml` があるディレクトリで `sudo docker compose ps` を実行する。
   - 確認ポイント: `filebeat`、`elasticsearch`、`kibana` などの各コンテナのステータス（STATUS）が `Up` になっているか確認する。
   - もしFilebeatだけがExited等で停止している場合は、ログの運び屋が不在であるため、ログがOpenSearch Dashboardsに届かない。その場合は `sudo docker compose restart filebeat` などで再起動を試みる。

---
## 補足4: ログを保存したまま、終了する手順、起動する手順
システムに不要なエラーログを残したり、起動時のファイルロックによるトラブルを防ぐための、一番きれいで安全なシャットダウン手順および起動手順を以下に示す。一日の作業の始まりと終わりに必ず実施する重要な手順となる。

### 終了する手順（外側から内側へ）
データの入り口（末端）から先へ停止していくことで、書き込み途中のデータクラッシュを防ぐ。

**1. ログ転送（Filebeat）の停止**
```bash
sudo docker stop filebeat-opensearch
```

**2. ログ生成（Zeek）の停止**
```bash
sudo /opt/zeek/bin/zeekctl stop
```

**3. 画面表示（OpenSearch Dashboards）の停止**
```bash
sudo docker stop opensearch-dashboards
```

**4. データベース（OpenSearch）の停止**
```bash
sudo docker stop opensearch
```

**5. ゲストOS（Monitor Server）のシャットダウン**
```bash
sudo shutdown -h now
```

### 起動する手順（内側から外側へ）
データを受け止める土台（コア）から順に起動し、準備が整ってからデータを安全に流し込む。

**1. データベース（OpenSearch）の起動**
```bash
sudo docker start opensearch
```
*(※完全に起動するまで数十秒待機する)*

**2. 画面表示（OpenSearch Dashboards）の起動**
```bash
sudo docker start opensearch-dashboards
```

**3. ログ生成（Zeek）の起動（deploy）**
```bash
sudo /opt/zeek/bin/zeekctl deploy
```

**4. ログ転送（Filebeat）の起動**
```bash
sudo docker start filebeat-opensearch
```
これにより、Filebeatが停止期間中に出力されたログの差分も含めて安全に読み取り、OpenSearch Dashboardsへの転送を再開する。

---

## 補足5: ログの全クリアと監視の再スタート手順
検証テストを何度も繰り返す中で、「これまで蓄積された過去のログデータやエラーをすべてリセットし、まっさらな状態から再検証を始めたい」という場合の、全体の停止・削除・再開の基本的な流れを以下に示す。

### 1. 各モジュールの停止
まずシステム全体を止めてログファイルへの書き込みをロックさせないようにする。
- **OpenSearchスタックの停止:** `docker-compose.yml` があるディレクトリで以下を実行。
  ```bash
  sudo docker compose down
  ```
- **Zeekの停止:**
  ```bash
  sudo /opt/zeek/bin/zeekctl stop
  ```

### 2. 蓄積されたデータの全削除（クリーンアップ）
- **Zeekのログファイル削除:** Spool（現在出力中）とLogs（アーカイブ済）の中身を強制的に全削除する。
  ```bash
  sudo rm -rf /opt/zeek/spool/zeek/*
  sudo rm -rf /opt/zeek/logs/*
  ```
- **OpenSearchのデータベース削除（※注意）:**
  DockerのVolumes（データベース）に保存されているOpenSearchの過去データを丸ごと消去する。
  一番手っ取り早いのは、使われていないDockerボリュームを一括削除する方法である。
  ```bash
  sudo docker volume prune -a
  ```
  *(※OpenSearch用ディレクトリ内に直接 `data/` などのローカルマウントフォルダがある場合は `sudo rm -rf ./data/*` のように手動でフォルダ内を空にする必要があります)*

### 3. クリーンスタート（再開）
- **OpenSearchスタックの起動:**
  ```bash
  cd /home/kali/localwork/opensearch_stack
  ./start_elk.sh
  ```
  *(※OpenSearchが完全に立ち上がるまでOpenSearch Dashboardsはアクセスできないため、数分間待機する)*
- **Zeekの起動:**
  ```bash
  sudo /opt/zeek/bin/zeekctl start
  ```
- その後、OpenSearch Dashboards（`http://<IPアドレス>:5601`）へアクセスし初期設定（Data Viewの作成等）を再度行ったうえでトラフィックを流し、一から検証を開始する。

---

## 補足6: トラブルシューティング（パケットは来ているのにOpenSearch Dashboardsに表示されない場合）
`tcpdump` 等で対象のインターフェース（`enp0s3`など）にパケットが届いていることが確認できるにもかかわらず、OpenSearch DashboardsのDiscover画面にログが表示されない、または `error.message: Error decoding JSON...` などのエラーが出る場合の解決手順です。

これは主に、**「Zeekのログ出力がJSON形式になっていない」** または **「過去の非JSON形式の古いログをFilebeatが読み込もうとしてパースエラーを起こしている」** ことが原因です。以下の手順で古いログを消去し、設定を再反映させてクリーンスタートを行います。

### 1. プロセスの安全な停止
書き込み・読み込み中のファイル破損を防ぐため、ZeekとFilebeatを停止します。
```bash
sudo /opt/zeek/bin/zeekctl stop
sudo docker stop filebeat
```

### 2. 古いログファイルの全消去
エラーの原因となっている古い非JSON形式のログファイルを完全に削除します。
```bash
sudo rm -rf /opt/zeek/spool/zeek/*
sudo rm -rf /opt/zeek/logs/*
```

### 3. JSON出力設定の確実な反映
Zeekがログを確実にJSON形式で出力するように設定を追加し、再デプロイします。
```bash
# 設定ファイルへの追記（既に記述済みの場合は上書きされず安全です）
echo '@load policy/tuning/json-logs.zeek' | sudo tee -a /opt/zeek/share/zeek/site/local.zeek

# Zeekの設定反映と起動（deploy）
sudo /opt/zeek/bin/zeekctl deploy
```

### 4. Filebeatの再稼働
最後にFilebeatを起動し、新しく生成されたクリーンなJSONログの転送を再開させます。
```bash
sudo docker start filebeat
```

完了後、通信を発生させて数分待機し、OpenSearch DashboardsのDiscover画面でIPアドレス（`id.orig_h`、`id.resp_h` 等）が正しく分解されて表示されていれば復旧完了です。

### 5. （オプション）OpenSearch内の過去のエラーログも完全に消去したい場合
上記1〜4の手順で新しく発生したログは正しく可視化されるようになりますが、OpenSearch Dashboardsの画面上には過去の「Error decoding JSON」等のエラーログも混ざって表示されたままになります。
もしこれらの過去データもすべて消し去り、データベースを完全にまっさらな状態からやり直したい場合は、Zeekのログ削除に加えて以下の「全体クリア手順」を実施してください。

```bash
# 1. OpenSearchスタック全体を停止・コンテナ削除
cd /home/kali/localwork/opensearch_stack
sudo docker compose down

# 2. OpenSearchの保存データ（Dockerボリューム）を完全に削除
# （※警告が出たら 'y' を押してエンター）
sudo docker volume prune -a

# 3. OpenSearchスタックを再起動
./start_elk.sh
```

※注意：この操作を行うと、OpenSearch Dashboards上で作成した「Data View」などもすべてリセットされるため、起動完了後に再度OpenSearch Dashboardsへアクセスし、初期設定（Data View `filebeat-*` の作成）からやり直す必要があります。
