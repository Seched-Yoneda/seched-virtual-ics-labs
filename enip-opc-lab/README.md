# OPC UA & EtherNet/IP Robot Simulation Lab

このディレクトリは、**OPC UA** および **EtherNet/IP** 通信を用いた「MES-PLC-ロボット連携シミュレーション」の仮想環境（Dockerコンテナベース）を提供します。
製造現場のネットワーク環境を模倣し、各コンポーネントが独立したコンテナとして相互に通信を行い、ロボットアームの物理シミュレーションと連動する構成となっています。

## 構成要素 (コンテナ)

- **MES (`fa_sim_mes`)**: OPC UA Serverとして生産オーダーや状態を管理。
- **HMI (`fa_sim_hmi`)**: Webダッシュボードを提供し、OPC UA / ENIP Clientとして稼働。
- **PLC (`fa_sim_plc`)**: OPC UA Client 兼 EtherNet/IP Client / Server として、MESとRobot間の制御ロジックを担う。
- **Robot (`fa_sim_robot`)**: EtherNet/IP Server。内部でPyBullet物理エンジンを稼働させ、ホストOS上に3Dシミュレーション画面を描画する。

## ファイルとディレクトリ構造

- `EtherNet-IP通信とOPC UAを利用するロボットシミュレーション環境の構築.md`
  - 本環境の詳細なアーキテクチャ、構築手順、ネットワーク設定、パケットキャプチャ設定などを記載した総合手順書です。環境構築の際は必ず最初にご確認ください。
- `docker-compose.yml`
  - 4つのコンテナのビルド、起動順序（depends_on）、およびMacvlanネットワークを定義するファイルです。
- `start.sh`
  - RobotコンテナのGUI（PyBullet）をホストマシンのディスプレイに描画するための環境変数（`DISPLAY`）および `xhost` アクセス権限を自動設定する起動準備スクリプトです。
- `hmi/`, `mes/`, `plc/`, `robot/`
  - 各コンテナをビルドするための `Dockerfile` と、実行されるアプリケーションソースコード（Pythonなど）が格納されたディレクトリです。

## 実行方法（概要）

1. 詳細な手順は必ず **[構築手順書](./EtherNet-IP通信とOPC UAを利用するロボットシミュレーション環境の構築.md)** を参照してください。
2. `./start.sh` を実行して、コンテナからのGUI描画権限をセットアップします。
3. `sudo docker-compose up -d --build` コマンドで、シミュレーション環境全体を起動します。
4. 終了時は `sudo docker-compose down` でコンテナとネットワークをクリーンアップします。
