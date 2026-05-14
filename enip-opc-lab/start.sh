#!/bin/bash

echo "=== GUI環境を動的に検知してシミュレータを起動します ==="

# 1. ログイン中のユーザーのデスクトップセッションから環境変数を動的に取得
export $(ps eww -u $USER | grep -E 'gnome-session|Xwayland' | grep -o 'XAUTHORITY=[^ ]*' | head -n 1)
# Xwayland の実際の待ち受けポート（引数）から DISPLAY を取得する
export DISPLAY=$(ps eww -C Xwayland -o cmd | grep -o ':[0-9]\+' | head -n 1)

# 万が一取得できなかった場合の安全策（従来の :0 にフォールバック）
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
    echo "警告: GUIセッションを自動検知できなかったため、デフォルトの DISPLAY=:0 を使用します。"
else
    echo "検知された DISPLAY: $DISPLAY"
fi

# 2. Xサーバーへのアクセスをローカルroot（Dockerコンテナ）に許可
# （エラー出力は無視し、実行が成功したことだけを担保）
xhost +local:root > /dev/null 2>&1
echo "Xサーバーのアクセス許可 (xhost) を設定しました。"

# 3. ロボットシミュレータを描画するDISPLAY番号が動的に変わっても対応できるようにする
# （sshで起動する場合など、設定したDISPLAY環境変数が sudo に
# 引き継がれないので、docker-composeが参照する .env ファイルを生成）
echo "DISPLAY=$DISPLAY" > .env
echo ".env ファイルを最新のディスプレイ設定で更新しました。"

echo "=== 環境の準備が完了しました ==="
echo "続いて sudo docker-compose up -d を実行してコンテナを起動してください。"
