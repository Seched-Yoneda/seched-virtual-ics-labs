#!/bin/bash

# 外付けHDDがマウントされているかチェック
if mountpoint -q /opt/opensearch_data; then
    echo -e "\e[32m[OK] 外付けHDDのマウントを確認しました。docker-compose を起動できます。\e[0m"
else
    echo -e "\e[31m【警告】外付けHDDが接続（マウント）されていません！\e[0m"
    echo -e "\e[31mVMのディスク枯渇を防ぐため、docker-compose の起動を中止してください。\e[0m"
    echo "外付けHDDを接続し、マウントされたことを確認してから再度実行してください。"
    exit 1
fi
