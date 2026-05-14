# ZeekとOpenSearchによる異常検知設定手順書 (ポートスキャン検知編)

本ドキュメントでは、Zeekでネットワーク上のポートスキャンを検知し、OpenSearch Stack (OpenSearch Dashboards) を通じてアラート通知を行うための設定手順を記載する。

---

## 1. Zeek側：スキャン検知ロジックの導入

モダンなZeek環境（バージョン5.0以降）では標準のポートスキャン検知スクリプトが廃止されているため、パッケージマネージャー（`zkg`）を利用して、実績のある外部パッケージ（`zeek/ncsa/bro-simple-scan`）をインストールする。

### 1.1. 検知パッケージのインストール
ZeekにNCSA（米国立スーパーコンピュータ応用研究所）が提供する高パフォーマンスなポートスキャン検知ロジックを導入する。

- **実行コマンド**:
  ```bash
  # スキャン検知パッケージのインストール
  sudo /opt/zeek/bin/zkg install zeek/ncsa/bro-simple-scan
  ```
  ※ コマンド実行後、`Proceed? [Y/n]` と聞かれた場合は `Y` を入力してエンターを押す。

### 1.2. 設定の反映（deploy）
パッケージのインストール後、Zeekの構成を再構築して変更を反映（デプロイ）する。（`local.zeek` に標準で記載されている `@load packages` により、インストールしたパッケージが自動で読み込まれる）

```bash
sudo /opt/zeek/bin/zeekctl deploy
```

> [!NOTE]
> これにより、特定のIPから短時間に多数のポートへ接続を試みる挙動が観測されると、自動的に `/opt/zeek/spool/zeek/notice.log` へ `Scan::Port_Scan` という識別子でアラートログが書き込まれるようになる。

---

## 2. 動作確認手順

Zeekのスキャン検知パッケージが正しく動作し、ログが出力されるかをテストする。
（※このテストによって初めて `notice.log` が生成され、後続のOpenSearch側の設定である「フィールドの自動学習」がスムーズに行えるようになる）

### 2.1. Nmapによる疑似攻撃
監視対象ネットワーク `10.7.1.0/24` に対して、ポートスキャンを実行する。

```bash
# 例: 10.7.1.0/24 全体への、高速なTCPポートスキャン
nmap -Pn -sS -T4 10.7.1.0/24
```
（※Nmapコマンドがインストールされていない環境の場合は、Python等を用いて複数ポートへ連続アクセスするスクリプトなどで代用可能）

### 2.2. Zeekログでの発報確認
ターミナルで以下のコマンドを実行し、アラートが記録されているか確認する。
```bash
sudo tail -f /opt/zeek/spool/zeek/notice.log
```
`Scan::Port_Scan` や `Scan::Random_Scan` などの文字列が含まれるJSON行が出力されていれば、Zeek側の検知は成功。

---

## 3. OpenSearch側：インデックスパターン（データのカタログ）の作成

Zeekからのデータ（アラートログ）が届いたら、OpenSearch Dashboardsにそれを認識させるための「インデックスパターン」を作成する。

1. ブラウザでOpenSearch Dashboards（例： `http://10.7.1.32:5601`）にアクセスする。
2. 画面左側のメニュー（ハンバーガーアイコン）を開き、一番下の **[Stack Management]** をクリックする。
3. **[Index Patterns]** を選択し、画面右側の青い **[Create index pattern]** ボタンをクリックする。
4. **Step 1: Define index pattern**
   - `Index pattern name` の入力欄に半角で **`filebeat-*`** と入力する。（※下に緑色で「Your index pattern matches 1 source.」等と出ればOK）
   - 右下の **[Next step]** をクリックする。
5. **Step 2: Configure settings**
   - `Time field` のプルダウンを開き、**`@timestamp`** を選択する。
6. 右下の **[Create index pattern]** をクリックする。

これで、Zeekから届いたすべてのログ項目（フィールド）がカタログとしてDashboardsに学習される。

---

## 4. OpenSearch側：OpenSearch Dashboardsでのアラート通知設定

学習されたフィールド情報をもとに、Dashboards上で視覚的なアラート（インシデント履歴）を記録する設定を行う。

### 4.1. 通知ルール（Monitor）の作成手順
（※注意：Kibana時代に必要だった `xpack.security` などの暗号化キー設定は、OpenSearchでは完全に不要であるため、設定ファイルの追記や再起動は不要である）

1. 左側メニューの「OpenSearch Plugins」カテゴリ配下にある **[Alerting]** を選択する。
2. 画面上部のタブから **[Monitors]** を選択し、青い **[Create monitor]** ボタンをクリックする。
3. **Monitor details** に以下を入力する。
    - **Monitor name**: `Port Scan Alert (10.7.1.0/24)`
    - **Monitor type**: `Per query monitor`
    - **Monitor defining method**: `Visual editor`
4. **Schedule** に以下を入力する。
    - **Frequency**: `By interval`
    - **Run every**: `1 Minutes` （1分間隔で監視を実行する）

### 4.2. 条件（クエリ）の定義
さらに画面を下へスクロールし、判定基準を以下のように入力する。

1. **Data source**:
   - **Index**: 検索窓に `filebeat-*` と入力してEnterを押す（※プルダウンには最初表示されないため手入力する）。
   - **Time field**: プルダウンから `@timestamp` を選択する。
2. **Query**:
   - **Metrics**: デフォルトの `COUNT OF documents` のままでよい。
   - **Time range for the last**: デフォルトの `1 hour(s)` から **`1 minute(s)`** に変更する。（※直近1分のログだけを対象にするため。先ほどのScheduleの間隔と合わせるのが重要）
   - **Data filter**: `+ Add filter` をクリックし、以下の条件を設定してSaveする。
     - Field: `note`
     - Operator: `is`
     - Value: `Scan`
     （※Zeekが検知したスキャンイベント（Scan::Port_Scan 等）は「Scan」という単語が含まれるため、これで全てを拾い上げることができます）

3. 画面一番下の **[Create]** ボタンをクリックしてMonitorを保存する。

### 4.3. トリガーとアクションの設定
Monitorを作成すると、Monitorの詳細画面が表示される。画面に「This monitor has no triggers configured.」と表示されるため、**[Edit monitor]** をクリックして編集画面に入る。
画面を一番下までスクロールし、「Triggers (1)」という枠の中にある **`> New trigger`** という文字（アコーディオン）をクリックして設定を展開する。（※この時、青い `[Add trigger]` ボタンを押してしまうと2つ目の枠ができてしまうため押さないこと）

1. **Trigger name**: デフォルトの `New trigger` から `Scan Detected` 等に変更する。
2. **Severity level**: `1 (Highest)` を選択する。（※FA環境でのポートスキャンは攻撃の初期段階を示す重大な兆候であるため）
3. **Trigger condition**: デフォルトの `IS ABOVE 0` のままでよい。（1件でも発生したら発火）
4. **Actions** (外部への通知先の設定):
    - 今回はDashboardsの画面上でアラート履歴を確認できれば良いため、外部連携（Slack等）が不要な場合はActionは未設定（空欄）のままで構わない。
    - ※Webhook等を追加したい場合はここでDestinationを作成する。
4. 画面一番下の **[Update]** ボタンをクリックしてMonitorの変更を保存する。

これ以降、条件に合致する不正な通信が検知されると、Alerting画面の **[Alerts]** タブにアラート履歴（インシデント）として自動的に記録されるようになる。

### 4.4. アラートの発報確認（最終テスト）
設定が完了したら、実際にアラートが画面上で発報される（赤く表示される）かを確認する。

1. **Zeekのログ抑制（Suppression）のリセット**
   Zeekは一度スキャンを検知すると「1時間は同じアラートを出さない」という負荷軽減機能が働くため、先ほどの「2. 動作確認」から連続してテストを行う場合は、以下のコマンドでZeekを再起動して記憶をリセットする。
   ```bash
   sudo /opt/zeek/bin/zeekctl restart
   ```
2. **Nmapの再実行**
   再度ポートスキャンを実行する。
   ```bash
   nmap -Pn -sS -T4 10.7.1.0/24
   ```
3. **Dashboardsでの発報確認**
   数分（スケジュールの1分間隔＋ログが届くまでのタイムラグ）待った後、Dashboards上で以下のいずれかの画面を確認する。（※待っても画面が変化しない場合は、F5キー等でブラウザの画面を「再読み込み（リロード）」すること）
   - **確認方法A**: 左側メニューの **[Alerting]** を開き、上部タブから **[Alerts]** を選択する。Stateが「Active」となったアラートの一覧が表示される。
   - **確認方法B**: 上部タブの **[Monitors]** から作成した `Port Scan Alert` をクリックして詳細画面を開く。中段の **[History]** グラフに赤い線が立ち、下部の **[Alerts]** リストにもインシデント履歴が表示される。

   （※無事にこれらの画面に「Scan Detected」が記録されれば、異常検知から通知までの全フローが完璧に動作している証拠である）

---

## 補足1：スキャンの種類とワイルドカード指定について
今回導入したZeekの検知パッケージ（`bro-simple-scan`）は、攻撃者の挙動を分析してスキャンの種類を以下のように自動で分類し、アラートの `note` フィールドに記録する。

- **`Scan::Port_Scan`**: 1つのIP（1台のPC）に対して、複数のポートを手当たり次第にスキャンした場合。
- **`Scan::Address_Scan`**: 同じポート（例：Webの80番など）を、ネットワーク内の複数IPに順番にスキャンした場合。
- **`Scan::Random_Scan`**: ネットワーク全体の複数IPに対し、複数ポートを無差別にスキャンした場合。（※ `/24` などのネットワーク全体に対するNmap実行時に分類される）

OpenSearch DashboardsのKQLクエリにおいて `note: Scan\:\:*` とアスタリスク（ワイルドカード）を指定することで、これらすべての異常行動を漏れなく1つのアラートルールで検知・通知できるようになっている。

**※ KQLにおけるワイルドカード検索の注意点**
KQLにおいてコロン（`:`）は特殊文字（フィールド名の区切り文字）として扱われる。そのため、ワイルドカード検索時にダブルクォーテーションで全体を囲んでしまうと、アスタリスク（`*`）がワイルドカードではなく「文字そのもの」として解釈されてしまい検索がヒットしない。これを回避するため、ダブルクォーテーションは使わず、`\`（バックスラッシュ）を用いてコロンをエスケープ（`\:`）する必要がある。

## 補足2：検知しきい値の調整
デフォルトの検知が敏感すぎる場合や、逆に検知漏れがある場合は、導入した `bro-simple-scan` パッケージの仕様に基づき、`/opt/zeek/share/zeek/site/local.zeek` にて関連する定数（しきい値等）を `redef` 構文で上書きすることで感度を調整可能である。

## 補足3：連続テスト時のログ抑制（Suppression）機能に関する注意点
Zeekはログのフラッド（大量発生）によるサーバー負荷を防ぐため、デフォルトで**「同一IPからの同一種類のアラートは、一度検知するとその後1時間（3600秒）は無視してログに出力しない」**という抑制機能（`suppress_for: 3600.0`）が働いている。

そのため、ペネトレーションテスト（Nmap）を短時間に何度も実行した場合、2回目以降はZeekのログが出力されず、結果としてOpenSearch Dashboardsのアラートも反応しなくなるという事象が発生する。
設定変更後のテストなどを連続して行いたい場合は、以下のコマンドでZeekプロセスを再起動し、メモリ上の抑制状態（記憶）をリセットしてからNmapを実行すること。

```bash
# Zeekを再起動し、ログ抑制状態をクリアする
sudo /opt/zeek/bin/zeekctl restart
```

## 補足4：KQL（OpenSearch Dashboards Query Language）の書き方と便利なサンプル集
OpenSearch Dashboardsのルール条件（Define your query）に入力するKQLは、直感的にログを絞り込める検索構文である。基本的には `フィールド名: "検索したい値"` の形式で記述し、`and`、`or`、`not` などの論理演算子を組み合わせて複雑な条件を作ることができる。

**【Zeek特有のフィールド名（通信の送信元・宛先）について】**
Zeekはネットワークの通信（コネクション）を記録する際、送信元と宛先を以下のような固有の名前（フィールド）で管理している。KQLでクエリを書く際には、これらを指定して検索する。

- **`id.orig_h`** : Originator Host（通信の送信元IPアドレス / 攻撃者側）
- **`id.resp_h`** : Responder Host（通信の宛先IPアドレス / 被害者側）
- **`id.orig_p`** : Originator Port（送信元のポート番号）
- **`id.resp_p`** : Responder Port（宛先のポート番号）

※ なお、Random_Scanのような「ネットワーク全体への無差別スキャン」の場合、被害者が複数にまたがり単一IPに特定できないため、Zeekは `id.resp_h` フィールド自体をログに生成しない仕様となっている点に注意が必要である。

**【異常検知で役立つKQLサンプル5選】**

1. **すべてのスキャン検知アラートを拾う（前方一致）**
   ```text
   note: Scan\:\:*
   ```
   *解説*: ワイルドカード `*` を使い、`Scan::Port_Scan` や `Scan::Random_Scan` など、頭に `Scan::` が付くすべての警告をまとめて検知する。コロン（`:`）は特殊文字のため `\` でエスケープしている。

2. **信頼できる送信元IP（脆弱性診断サーバー等）をアラートから除外する**
   ```text
   note: Scan\:\:* and NOT src: "10.7.1.100"
   ```
   *解説*: スキャンを検知しつつも、あらかじめ許可された特定のIP（例: 10.7.1.100）からの通信は正常な業務であるとしてアラートの対象外（ホワイトリスト化）にする。

3. **特定のネットワーク宛ての単一ホスト攻撃（Port_Scan）のみを監視する**
   ```text
   note: "Scan::Port_Scan" and id.resp_h: "10.7.1.0/24"
   ```
   *解説*: ネットワーク全体への無差別スキャン（Random_Scan）は無視し、指定したIP帯（`/24`）内の特定の1台を執拗に狙うポートスキャンに限定して検知する。

4. **パスワード推測（ブルートフォース攻撃）を検知する**
   ```text
   note: "SSH::Password_Guessing" or note: "FTP::Bruteforcing"
   ```
   *解説*: `or` を使うことで複数の条件を束ねる。Zeekのパスワード推測検知スクリプトが有効な場合、SSHやFTPに対するログイン試行アラートを検知する。

5. **特定の危険なポート（RDPやSSH）に対する通信自体を監視する**
   ```text
   id.resp_p: 3389 or id.resp_p: 22
   ```
   *解説*: スキャン検知（`notice.log`）に限らず、すべての通信ログ（`conn.log` 等）を対象にしたアラートを作る際に有効。WindowsのRDP（3389番）やLinuxのSSH（22番）へアクセスが発生した瞬間にアラートを上げる。

---

## 5. 発展：FA・制御システム（OT）向け特化型検知ルールの作成手順

本節では、仮想FA環境（FADockerHostなど）を標的とした実践的なサイバー攻撃（不正な端末からの操作、およびMITMによる通信改ざん）に対する、OpenSearch Dashboardsアラートルールの作成手順を解説する。

### 5.1. 不正な端末からの操作（サボタージュ）の検知

Kali Linux（攻撃者）などが、本来アクセス権のない制御用プロトコル（ENIP/CIPなど）を使用してPLC等を直接操作しようとする攻撃を検知する。

**【仮想FA環境のネットワーク構成（正規通信ホワイトリスト定義）】**
本手順では、以下の通信マッピングを仮想FA環境の正規な経路としとする。

| 送信元 (Source IP) | Sourceの役割 | 送信先 (Destination IP) | Destinationの役割 | プロトコル | トランスポート / ポート | 備考（通信の方向・内容） |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `10.7.1.3` (Browser) | Web Client | `10.7.1.41` (HMI) | Web Server | HTTP | TCP / `8080` | ブラウザからの画面アクセス・操作要求 |
| `10.7.1.41` (HMI) | OPC UA Client | `10.7.1.40` (MES) | OPC UA Server | OPC UA | TCP / `4840` | HMIからMESへのデータ収集・監視 |
| `10.7.1.42` (PLC) | OPC UA Client | `10.7.1.40` (MES) | OPC UA Server | OPC UA | TCP / `4840` | PLCからMESへの製造パラメータ取得・ステータス同期 |
| `10.7.1.41` (HMI) | ENIP Originator | `10.7.1.42` (PLC) | ENIP Target | EtherNet/IP | TCP / `44818` | HMIからPLCへのExplicit Message (Read/Write) |
| `10.7.1.41` (HMI) | ENIP Originator | `10.7.1.43` (Robot) | ENIP Target | EtherNet/IP | TCP / `44818` | HMIからRobotへのエラー発生操作 (Explicit) |
| `10.7.1.42` (PLC) | ENIP Originator | `10.7.1.43` (Robot) | ENIP Target | EtherNet/IP | TCP / `44818` | PLCとRobot間のタグ読み書き通信（制御指示・ステータス監視） |

**【検知ロジック】**
上記の通信ルールに基づき、要となる「PLCに対する制御用ポート（ENIP: 44818）の不正アクセス」を監視する。
正常な環境において、宛先がPLC (`10.7.1.42`) のENIP通信は HMI (`10.7.1.41`) からしか発生しない。したがって、HMI **以外**のIPからの通信をすべて異常（サボタージュの試み）として検知する。

**【OpenSearch Dashboardsルールの設定値】**

**【FA環境のネットワーク構成（前提）】**を考慮し、「最重要資産（PLC）」を守るためのルールを設定する。
基礎編第4章と同様に、左側メニューの **[Alerting]** を開き、上部の **[Monitors]** タブを選択してから **[Create monitor]** をクリックし、以下のように設定する。

**【Monitorの詳細】**
- **Monitor name**: `Unauthorized ENIP Access (PLC)`
- **Monitor type**: `Per query monitor`
- **Monitor defining method**: `Extraction query editor` を選択する。（※Visual editorは複数条件が設定できないため）
- **Schedule**: Frequency `By interval`, Run every `1 Minutes`

**【Indices（データソース）】**
- **Index**: 検索窓に `filebeat-*` と入力してEnterを押す。

**【Define extraction query（クエリ定義）】**
エディタ内の既存のコードをすべて消去し、以下のJSONコードをそのままコピー＆ペーストする。
（※これで「宛先がPLC、ポートがENIP、かつ送信元がHMI以外」かつ「直近1分のデータのみ」という複雑な条件が適用される）

```json
{
  "size": 0,
  "query": {
    "bool": {
      "filter": [
        {
          "range": {
            "@timestamp": {
              "from": "{{period_end}}||-1m",
              "to": "{{period_end}}",
              "include_lower": true,
              "include_upper": true,
              "format": "epoch_millis"
            }
          }
        },
        {
          "query_string": {
            "query": "id.resp_h: \"10.7.1.42\" AND id.resp_p: 44818 AND NOT id.orig_h: \"10.7.1.41\""
          }
        }
      ]
    }
  }
}
```

**【構文のテスト確認（推奨）】**
コード入力枠の右上にある **[Run]** ボタンをクリックする。右側の `Extraction query response` 枠にエラーが表示されず、`{ "took": ... "hits": ... }` のような正常なレスポンスが返ってくれば、JSONの構文は正しい状態である。
**【Monitorの保存】**
画面一番下の青い **[Create]** ボタンをクリックしてMonitorを保存する。画面が切り替わったら、タイトルの右にある **[Edit]** ボタン（または青い警告バナー内のリンク）をクリックして再度編集画面に入り、画面一番下のTriggersの枠から **[Add trigger]** ボタンをクリックする。

**【Triggerの設定】**
- **Trigger name**: `Sabotage Attempt Detected`
- **Severity level**: `1 (Highest)`
- **Trigger condition**: 既存のコードをすべて消し、以下の1行だけを貼り付ける。（「検知件数が0より大きい場合」という意味）
  ```painless
  ctx.results[0].hits.total.value > 0
  ```
  *(※ 下にある `Preview condition response` ボタンを押すと右側に結果が出ますが、現在は攻撃が発生していないため `false` や `No trigger results` と表示されていれば正常です)*
  *(※ その下にある **Actions** 欄はSlack等の外部通知用なので、今回は何も追加せず空欄のままで構いません)*

**【設定の完了】**
画面一番下にある青い **[Update]** ボタンをクリックして、トリガーとMonitorの設定を完了する。

---

**【追加：Robotに対する不正操作（成りすまし）の検知ルール】**
ブラウザ端末（`10.7.1.3`）などが乗っ取られ、攻撃者がそこから直接 Robot（`10.7.1.43`）へ偽の製造指示を送るような「成りすまし操作」を検知するためのルールを追加で作成する。

通信経路の定義上、Robotに対する正規のENIPアクセス元は HMI（`10.7.1.41`）と PLC（`10.7.1.42`）のみである。したがって、それ以外のIP（乗っ取られたブラウザ等）からの通信をすべて異常として検知する。

- **Monitor name**: `Unauthorized ENIP Access (Robot)`
- **Monitor defining method**: `Extraction query editor`
- **Indices**: Indexに `filebeat-*` と入力してEnter。
- **Define extraction query**: 以下のJSONを貼り付け。

```json
{
  "size": 0,
  "query": {
    "bool": {
      "filter": [
        {
          "range": {
            "@timestamp": {
              "from": "{{period_end}}||-1m",
              "to": "{{period_end}}",
              "include_lower": true,
              "include_upper": true,
              "format": "epoch_millis"
            }
          }
        },
        {
          "query_string": {
            "query": "id.resp_h: \"10.7.1.43\" AND id.resp_p: 44818 AND NOT (id.orig_h: \"10.7.1.41\" OR id.orig_h: \"10.7.1.42\")"
          }
        }
      ]
    }
  }
}
```

**【構文のテスト確認（推奨）】**
コード入力枠右上の **[Run]** ボタンをクリックし、右側の枠にエラーが返らないことを確認する。

**【Monitorの保存とTriggerの設定】**
画面一番下の **[Create]** を押して保存後、タイトルの右の **[Edit]** ボタンから編集画面に入り、一番下のTriggers枠にある **[Add trigger]** ボタンをクリックして以下のトリガーを追加する。

- **Triggerの設定**:
  - **Trigger name**: `Spoofing Detected`
  - **Severity level**: `1 (Highest)`
  - **Trigger condition**: `ctx.results[0].hits.total.value > 0` を貼り付ける。（※Previewで `No trigger results` や `false` が出ても正常です）
  - *(※ Actions欄は空欄のままで構いません)*

**【設定の完了】**
画面一番下にある青い **[Update]** ボタンをクリックして設定を完了する。

### 5.2. MITM（中間者攻撃）による通信改ざん・傍受の検知

Kali LinuxがARPスプーフィング等で経路に割り込み、通信内容の盗聴や改ざん（View of Manipulation）を行う攻撃を検知する。

**【検知ロジック】**
MITM攻撃によるパケットインジェクションや経路変更が発生すると、TCPのシーケンス不整合やMACアドレスの異常などが発生し、Zeekはこれを `weird.log`（奇妙な通信）として記録する。この `weird.log` の発生そのものを検知のトリガーとする。

**【OpenSearch Dashboards Monitorの設定値】**

Visual editorでは複雑な「or」条件が作りにくいため、今回は一番手軽な「すべての weird.log を監視対象にする」ルールを作成する。

**【Monitorの詳細】**
- **Monitor name**: `Abnormal Traffic / MITM Attempt`
- **Monitor defining method**: `Visual editor`
- **Data source**: Indexに `filebeat-*` と入力してEnter、Time fieldは `@timestamp` を選択。
- **Query**: Time range for the last を **`1 minute(s)`** に変更。
- **Data filter**:
  - Field: `log.file.path`
  - Operator: `is`
  - Value: `/opt/zeek/spool/zeek/weird.log` （※環境に合わせてZeekのweird.logのフルパスを指定する）

**【Monitorの保存】**
画面一番下の青い **[Create]** ボタンをクリックして保存する。画面が切り替わったらタイトルの右にある **[Edit]** をクリックし、画面一番下のTriggers枠から **[Add trigger]** を開く。

**【Triggerの設定】**
- **Trigger name**: `MITM or Anomaly Detected`
- **Severity level**: `1 (Highest)`
- **Trigger condition**: `IS ABOVE 0`
- *(※ Actions欄は空欄のままで構いません)*

**【設定の完了】**
画面一番下にある青い **[Update]** ボタンをクリックして設定を完了する。

**【解説：なぜIPベースのルールではMITMを防げず、weird.logが必要なのか？】**
前項（5.1）で設定した `Unauthorized ENIP Access` などの「IPアドレスのホワイトリスト」ルールでは、ARPスプーフィングを用いたMITM攻撃を検知できません。その理由は、攻撃が行われても**IPアドレス（L3レイヤー）は正常な端末のまま維持される**ためです。

具体的に、攻撃時のネットワーク上では以下の状況が発生しています。

**【状況1】HMIからPLCへデータを要求する場合**
- **HMIが送信する瞬間**: 宛先IPはPLC（`10.7.1.42`）だが、宛先MACアドレスは騙されて攻撃者Kali（`10.7.1.3`）のものになる。
- **Kaliが中継してPLCへ転送する瞬間**: 送信元IPはHMI（`10.7.1.41`）のままだが、送信元MACアドレスはKali（`10.7.1.3`）になる。
👉 **PLC側の視点**: IPアドレスのログ上は「HMIからの正常な要求」に見えるが、物理的にはKaliのMACアドレスからパケットが届いている。

**【状況2】PLCからHMIへ応答（データ）を返す場合**
- **PLCが送信する瞬間**: 宛先IPはHMI（`10.7.1.41`）だが、宛先MACアドレスは騙されて攻撃者Kali（`10.7.1.3`）のものになる。
- **Kaliが中継・改ざんしてHMIへ転送する瞬間**: 送信元IPはPLC（`10.7.1.42`）のままだが、送信元MACはKali（`10.7.1.3`）になる。
👉 **HMI側の視点**: IPアドレスのログ上は「PLCからの正常な応答」に見えるが、物理的にはKaliから改ざん済みのデータパケットが届いている。

**【Zeek（weird.log）がこれを検知できる理由（統計処理ではない）】**
なお、Zeekの `weird.log` は「過去のデータに基づいた統計的・確率的なアノマリ検知（Machine Learning等）」を**用いていません**。Zeek内部の**「プロトコル解析エンジン（ステートマシン）」**が、TCPなどのRFC（世界共通の規格）に違反する絶対的な矛盾を捉えることで検知しています。

攻撃者が通信を中継・改ざんする過程で、以下のような「プロトコル上の不自然な振る舞い」が必然的に発生します。
1. **TCPシーケンスの不整合**: 攻撃者がデータの中身を書き換えてサイズが変わると、TCPのシーケンス番号やAck番号に矛盾が生じます。
2. **パケットの重複や遅延**: 攻撃者のツールによる中継処理により、異常なタイムアウト、パケット重複、再送が発生します。
3. **MACアドレスの競合**: ARPスプーフィングにより、同一IPに対するMACアドレスの急激な変化や矛盾が生じます。

Zeekはこれらの「L2/L4レイヤーにおける物理的・構造的な矛盾」を的確に捉え、**`weird.log`（奇妙な通信）** として記録します。そのため、本項目のルールではIPのホワイトリストではなく「weird.logの発生そのもの」を監視のトリガーとしています。

---

**【さらに詳細な技術補足：ペイロード改ざんによるTCP同期破綻メカニズム】**
MITMで「データの改ざん」が行われた際、なぜTCPの規格の辻褄が合わなくなり、Zeekがそれを検知できるのか、より技術的なメカニズムを補足する。

1. **データサイズ変更によるSEQ/ACKのズレ**
   TCPは送信した「データ量（バイト数）」をシーケンス番号（SEQ）で厳格に管理している。
   もし攻撃者（Kali）がPLCからHMIへの応答データ「`Count=10`（8バイト）」を「`Count=9999`（10バイト）」に改ざんして転送したとする。
   - **HMI側の状態**: 10バイト受け取ったため、PLCに対して「次は（元のSEQ ＋ 10）番から送ってね」という **ACK** を返す。
   - **PLC側の状態**: 自分は8バイトしか送っていないのに、HMIから「＋10」のACKが返ってくる。これは「自分が送っていない未来のデータに対するACKが届いた」状態であり、TCPの規格上エラー（RST送信等）を引き起こす。
   このように、1バイトでもデータサイズが変わる改ざんを行うと、送信元と宛先の間で「これまでに送受信したバイト数」の同期が完全に破綻（Desynchronization）する。

2. **MITMツールによる「つじつま合わせ」の限界と痕跡**
   優秀なMITMツールは上記のエラーを防ぐため、改ざん以降の**すべてのパケットのSEQ/ACKをリアルタイムに書き換えてプロキシし続ける**。しかし、Zeekがネットワーク（SPANポート等）でこれを監視している場合、以下のような不自然な物理的挙動を逃さず捉える。
   - **`ACK_above_max_seq`**: Zeekが観測したパケット量よりも大きなACK番号が飛んできた（改ざんによりサイズが増えた証拠）。
   - **`TCP_seq_mismatch` / 重複パケット**: 攻撃者が元のパケットを完全にドロップできず、正規パケットと改ざんパケットの両方が流れた場合、「同じSEQ番号なのに中身が違うパケット」が観測される。

3. **IP TTL（生存期間）やTCPオプションの不連続性**
   通常同一セグメント内ではIP TTLは固定だが、Kali Linuxがルーティングして中継するとTTLが「1」減る。Zeekは同一TCPセッション中であるにも関わらず、突然TTLが減ったり、TCPウィンドウスケール（OS固有の特徴）がKaliのものにすり替わったりする変化も「Weird」として検知可能である。

要するに、MITMで通信を改ざんすると、送信元・宛先・監視装置（Zeek）の3者間で「今何バイト目まで通信したか」の同期が必ず崩れ、それを無理やり補正しようとするツールの挙動がRFC規格から逸脱するため、Zeekの解析エンジンがそれを捕まえるのである。

**【重要：高度なMITMツールによる検知回避と、次なる対策へのステップ】**
本手順書で設定した `weird.log` を用いる検知ルールは、パケットのドロップや初歩的なツールによるTCP破綻（Weird）を捉えるための**第一段階の防御**である。

しかし、実際のペネトレーションテスト等において、**「ペイロードのデータ長（バイト数）を変更せず、かつOSやNIC（ネットワークアダプタ）のTCPチェックサム・オフロード機能に再計算を完全に任せるような高度なMITMツール（例: enip_mitm_dynamic.py 等）」**を使用した場合、ネットワーク上に送出される改ざんパケットはRFC規格上「一切の矛盾がない完璧なTCP通信」に自動修復されてしまう。この場合、ZeekはTCPレベルの異常（Weird）を検知できない。

このような高度なインターセプト（傍受・改ざん）を確実に防ぐためには、表面的なTCPヘッダの監視から脱却し、**「多層防御」**へのステップアップが不可欠である。

1. **物理層（ARP）の監視**: 
   Zeekの追加パッケージ（`zeek/corelight/arp-spoofing` 等）を導入し、IPアドレスではなく「MACアドレスの不自然な変化（ARPスプーフィング）」を直接検知する。
2. **データ層（アプリケーション）の監視**: 
   Zeekが解読した通信の中身（`enip.log` や `cip.log`）に着目し、「平常時とは異なる異常な値」や「未定義のコマンド」が流れたことをアノマリとして検知する。

より実践的で強固なセキュリティを構築するため、次の **「第5章 発展：通信パターンの学習による異常検知（アノマリ検知）」** に進み、アプリケーション層のログを活用した機械学習による検知の導入を推奨する。

---

### 5.3. MACアドレスの監視によるARPスプーフィングの静的検知

発展編で解説した通り、MITM（ARPスプーフィング）の最も確実で初動が早い検知方法は「EthernetフレームのMACアドレスの急変」を静的ルールで捉えることである。ここではZeekのMACロギング機能を有効化し、IPアドレスの偽装を見破るルールを作成する。

**【手順1：ZeekのMACロギング有効化】**
ZeekはデフォルトではL3（IP）以上の情報をログ化するため、L2（MACアドレス）の記録機能を明示的にオンにする必要がある。

1. ターミナルを開き、Zeekの設定ファイル（`local.zeek`）の末尾に設定を追記する。
   ```bash
   echo '@load policy/protocols/conn/mac-logging' | sudo tee -a /opt/zeek/share/zeek/site/local.zeek
   ```
2. 設定を反映（デプロイ）する。
   ```bash
   sudo /opt/zeek/bin/zeekctl deploy
   ```
これで、以降の通信ログ（`conn.log` 等）に `orig_l2_addr`（送信元MAC）と `resp_l2_addr`（宛先MAC）が記録され、OpenSearch側へ転送されるようになる。

**【手順2：OpenSearch Dashboardsのアラートルール作成】**
「IPアドレスは正規のHMI（`10.7.1.41`）を名乗っているが、物理的なMACアドレスがHMIのものではない（＝Kali等にスプーフィングされている）」という矛盾を突くクエリを作成する。

1. 左側メニューの **[Alerting]** から **[Monitors]** > **[Create monitor]** を開く。
2. **Monitor details**:
   - **Monitor name**: `ARP Spoofing Detected (MAC Anomaly)`
   - **Monitor type**: `Per query monitor`
   - **Monitor defining method**: `Extraction query editor`
   - **Schedule**: Frequency `By interval`, Run every `1 Minutes`
3. **Data source**: Indexに `filebeat-*` を指定。
4. **Define extraction query**: 以下のJSONを貼り付ける。
   *(※ここでは、FAシミュレーター環境で事前に固定設定されたHMIの正規MACアドレス `02:42:0a:07:01:29` を指定している)*

```json
{
  "size": 0,
  "query": {
    "bool": {
      "filter": [
        {
          "range": {
            "@timestamp": {
              "from": "{{period_end}}||-1m",
              "to": "{{period_end}}",
              "include_lower": true,
              "include_upper": true,
              "format": "epoch_millis"
            }
          }
        },
        {
          "query_string": {
            "query": "id.orig_h: \"10.7.1.41\" AND NOT orig_l2_addr: \"02:42:0a:07:01:29\""
          }
        }
      ]
    }
  }
}
```

**【構文のテスト確認（推奨）】**
コード入力枠右上の **[Run]** ボタンをクリックし、右側の枠にエラーが返らないことを確認する。

**【Monitorの保存とTriggerの設定】**
画面一番下の青い **[Create]** ボタンを押してMonitorを保存する。画面が切り替わったら、タイトルの右にある **[Edit]** ボタンから再度編集画面に入り、一番下のTriggers枠にある **[Add trigger]** ボタンをクリックして以下のトリガーを追加する。

- **Triggerの設定**:
  - **Trigger name**: `MAC Spoofing Detected`
  - **Severity level**: `1 (Highest)`
  - **Trigger condition**: 既存のコードをすべて消し、以下の1行を貼り付ける。（件数が0より大きい場合発火）
    ```painless
    ctx.results[0].hits.total.value > 0
    ```
    *(※ 下のPreviewボタンを押して `false` や `No trigger results` が出れば正常です)*

**【設定の完了】**
画面一番下にある青い **[Update]** ボタンをクリックして、トリガーの設定を完了する。

**【解説】**
このルールにより、「10.7.1.41（HMI）からの通信」としてネットワークを流れているが、送信元MACアドレスが事前に登録したHMIの正規MACではない（＝Kali Linux等によるARPスプーフィング）瞬間に即座にアラートが発火する。これがL2レイヤーの確実な静的防御（第一の壁）となる。

**【運用上の重要事項：コンテナ環境でのMACアドレス固定化】**
本番の工場環境における「機器故障による部品交換」と同様に、Dockerなどのコンテナ環境ではコンテナを再生成（`down` および `up --build`）するたびに、仮想ネットワークインターフェースに**新しいランダムなMACアドレス**が割り当てられる。
この状態では、コンテナを作り直すたびに当ルールが「MACアドレスの不一致」として誤検知（False Positive）を起こしてしまう。そのため、MACアドレスベースの異常検知を安定して検証（ペネトレーションテスト等）するためには、監視対象のFA環境の `docker-compose.yml` において、以下のように各コンテナのMACアドレスを静的に固定した。仮想環境としては安定した検知ルールを作れるが、機器変更によるMACアドレスの変更が発生する実環境では、誤検知が発生するルールとなる。

```yaml
# FADockerHost / docker-compose.yml の設定例
  hmi:
    build: ./hmi
    container_name: fa_sim_hmi
    mac_address: 02:42:0a:07:01:29  # ← コンテナを再生成してもMACアドレスが変わらないように固定
    networks:
      fa_network:
        ipv4_address: 10.7.1.41
```

---

### 5.4. 攻撃検知の確認手順（簡易版）

設定したルール（サボタージュおよびMITM）が正しく動作するかをテスト（ペネトレーションテスト）する際は、本格的な認証機能（Elastic Security等）の設定を行う前の「第一段階」として、以下の2つの方法でOpenSearch Dashboardsの検知ロジックを監視・確認する。

**1. ターミナル画面（Server log）でのリアルタイム監視**
OpenSearch DashboardsのGUIを表示しているブラウザタブと並行して、ターミナルを開き、MonitorServe(10.7.1.32)にkaliユーザでログインし以下を実行する。
```bash
sudo docker logs -f opensearch-dashboards
```
別のターミナルから攻撃（サボタージュスクリプトやARPスプーフィング等）を実行した直後、画面上に設定した『警告: 通信の改ざん・傍受...』等のアラートテキストがリアルタイムで流れてくれば、検知ロジックは正常に動作している。

**2. OpenSearch Dashboardsの画面（GUI）でのアラート履歴の確認**
ブラウザのOpenSearch Dashboards画面から、アラートの発火履歴を視覚的に確認する。
1. 左側メニューの `Management` から **「Stack Management」 ＞ 「Rules」** を開く。
2. 作成したルールの名前（例: `Abnormal Traffic / MITM Attempt (weird.log)` などの青字リンク）をクリックして詳細画面を開く。
3. 画面下部の **「Alert history（アラート履歴）」** のタブを確認し、攻撃を実行した時刻にアラート（ルールにマッチした記録）が残っていれば成功である。

*(※上記の簡易テストで検知ロジックの正しさが完全に証明できた後、実運用フェーズとしてパスワード認証を有効化し、「Elastic Security」アプリの専用ダッシュボードやSlack通知等の高度な機能へステップアップすることを推奨する)*

### 5.5. アラートが鳴らない場合の切り分け手順

`sudo docker logs -f opensearch-dashboards` を監視していても `Abnormal Traffic / MITM Attempt (weird.log)` のアラートテキストが出ない場合、以下の手順で原因を切り分けます。

**1. Zeekが検知していないのか？ OpenSearchが検知していないのか？**
大元のZeek自体が異常を検知して `weird.log` にログを出力しているかを確認します。ターミナルで以下のコマンドを実行し、ファイルのタイムスタンプと中身を調べてください。

```bash
# weird.log のタイムスタンプを確認
sudo ls -la /opt/zeek/spool/zeek/weird.log

# weird.log の最新の中身（アラート有無）を確認
sudo tail -n 20 /opt/zeek/spool/zeek/weird.log
```

- **ログに攻撃対象のIPに関する異常（Alert）が記録されていない場合:**
  Zeekが攻撃を検知できていません。（※「高度なMITMツールによる検知回避」に該当し、TCPレイヤーの矛盾が発生していない可能性が高いです）
- **ログに異常（Alert）が記録されている場合:**
  Zeekは正しく検知していますが、OpenSearch（OpenSearch Dashboards）側のルールのクエリ条件（KQLの記述や対象IPの指定）が適切ではありません。設定したルールを見直してください。

### 5.6. アラート監視のベストプラクティス（遅延と通知設定の理解）

アラートの運用・テストを行う上で、OpenSearch Dashboardsのステータス遷移や通知頻度、およびZeekのタイムアウト仕様に関する以下の知識が不可欠です。

**1. OpenSearch Dashboardsの「Status」と「Action frequency」の役割の違い**
- **Status（Active / Recovered）**: 画面（UI）上で現在の状況を把握するための状態表示です。対象時間内にログがあれば「Active」、なければ「Recovered」となります。
- **Action frequency**: アクション（通知）を実行する頻度を決める設定です。
  - `On check intervals`（毎分チェック時）: テストや検証用。Activeである限り毎分アラートが出力されるため、攻撃が検知されていることを漏れなく確認できます。
  - `On status changes`（ステータス変化時のみ）: 実運用（SOC/CSIRT業務）用。Activeに変化した瞬間に1度だけ通知を行うことで、アラート疲労（スパム化）を防ぎます。実運用ではこの設定にし、通知を受けたらOpenSearch Dashboards画面のStatusを見て状況を判断します。

**2. アラート発報の「遅延（タイムラグ）」の正体**
攻撃からアラート発報まで数分の遅延が発生する場合、システムの不具合ではなく以下の仕様が組み合わさった結果です。
- **OpenSearch Dashboardsのパトロール周期**: OpenSearch Dashboardsは1分間隔などのスケジュールで検索を行うため、ログが届いてからアラート発報まで最大1分程度の「スケジュール待ち」のタイムラグが発生します。
- **ZeekのTCPタイムアウト待ち**: セッションを綺麗に閉じない（FINを送らない）攻撃ツールによる通信の場合、Zeekは「通信がまだ続くかもしれない」と判断し、デフォルトで約5分間の無通信タイムアウトを待ってからログを書き出します。この仕様により、数分の発報遅延が正常な挙動として発生します。
  - *(※検証環境でこの遅延を短縮したい場合は、`/opt/zeek/share/zeek/site/local.zeek` に `redef tcp_inactivity_timeout = 30secs;` を追記してデプロイします)*
  - *(※検証スクリプト側で `cpppo` 等のネイティブライブラリを用い、プロトコルレベルで綺麗に通信を切断させれば、Zeekは即座にログを書き出します)*

---

## 6. 発展：通信パターンの学習による異常検知（アノマリ検知）

シグネチャ（決められたルール）ベースの検知からステップアップし、平常時の通信パターンを学習して「いつもと違う振る舞い」を検知するアプローチには、大きく分けて以下の2つの方法がある。外付け大容量ストレージ（HDD）に蓄積された長期的なログデータを最大限に活用できるため、本格的な運用フェーズでの導入を推奨する。

### 6.1. Zeek内蔵の統計的異常検知（SumStatsフレームワーク）

Zeekに内蔵された `SumStats`（Summary Statistics）フレームワークを使用し、通信量や頻度のベースラインを独自に計算して検知する方法。

**【特徴と導入手順】**
- **メリット**: Zeekプロセス内で完結するため軽量で高速。追加ライセンスも不要。
- **デメリット**: 統計の計算式やしきい値をZeekスクリプト（プログラミング）として独自に記述する必要がある。
- **導入の流れ**:
  1. `/opt/zeek/share/zeek/site/local.zeek` 等に独自のスクリプトを追記する。
  2. 観測（Observe）処理として、「1分ごとの各IPの送信バイト数」などを計測し続ける。
  3. 計算（Reduce）処理として、「過去15分間の平均値と標準偏差」などを定期的に算出。
  4. 判定処理として、「現在の値が平均値＋標準偏差の3倍を超えたら」`notice.log` に異常（WeirdやNotice）を出力させる。
  5. 出力されたログを、OpenSearch Dashboardsの `OpenSearch query` ルールで拾って通知する。

### 6.2. OpenSearch（OpenSearch Dashboards）の機械学習（Machine Learning）による検知

OpenSearchに標準搭載されている高度な機械学習（Anomaly Detection）プラグインを使用し、データから自動で平常時のパターン（通信の周期性など）を学習させ、未知の異常をスコア化して検知する方法。1TBの外部ストレージに蓄積した過去ログの真価を最も発揮できるアプローチである。

**【特徴】**
- **メリット**: Elastic Stack等とは異なり、OpenSearchでは**有償ライセンス不要で完全に無料（制限なし）**で利用可能である。しきい値の手動調整が不要で、「昼間は通信が多く夜は少ない」といった複雑な周期性もAIが自動で学習し、グラフで直感的に異常を視認できる。
- **デメリット**: AIが「正常な状態（ベースライン）」を正確に把握するまでに、一定時間（正常な通信ログの蓄積）の学習期間が必要になる。

**【具体的な設定手順について】**
機械学習（Anomaly Detection）を用いた高度な検知モデルの構築手順および詳細なチューニング方法については、以下のドキュメントにて解説している。
👉 **[ZeekとOpenSearchによる異常検知設定手順書（発展編）.md](./ZeekとOpenSearchによる異常検知設定手順書（発展編）.md)**
