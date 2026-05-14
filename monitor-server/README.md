# Monitor Server

このディレクトリは、**Zeek** と **OpenSearch** を用いた異常検知基盤（モニターサーバー）の構築・設定に必要なファイル群を管理しています。
仮想環境上でネットワークトラフィックを監視し、OpenSearchおよびOpenSearch Dashboardsで可視化・分析するためのシステム構成を提供します。

## 構成要素
- **OpenSearch / OpenSearch Dashboards**: ログの蓄積・検索と可視化の基盤 (`docker-compose.yml`で定義)。
- **Filebeat**: ZeekのログをパースしてOpenSearchに転送するためのエージェント (`filebeat.yml`で設定を定義)。
- **Zeek**: ネットワークトラフィックを解析し、JSON形式のログを出力するNIDS。

## ファイル一覧

### 設定・構成ファイル
- `docker-compose.yml` : OpenSearch, OpenSearch Dashboards, Filebeatのコンテナ群を起動するための定義ファイル。
- `filebeat.yml` : Filebeatの動作・ログ転送先設定。
- `CheckExternalHDD.sh` : 外付けHDD（マウントポイント）の存在チェック等を行うユーティリティスクリプト。

### 手順書（ドキュメント）
1. `ZeekとOpenSearchによる異常検知基盤構築手順書（Step2-Zeek常駐稼働編）.md`
2. `ZeekとOpenSearchによる異常検知基盤構築手順書（Step3-OpenSearch連携・仮想ディスク編）.md`
3. `ZeekとOpenSearchによる異常検知基盤構築手順書（Step4-OpenSearch連携・外付けHDD編）.md`
4. `ZeekとOpenSearchによる異常検知設定手順書（基礎編）.md`
5. `ZeekとOpenSearchによる異常検知設定手順書（発展編）.md`

各手順書を参照しながら、環境の構築と異常検知ルールの設定を進めてください。
