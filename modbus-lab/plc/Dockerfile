FROM ubuntu:24.04

# コンパイルに必要なパッケージのインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    libmodbus-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# ソースコードをコンテナ内にコピー
WORKDIR /app
COPY server.c .

# Cプログラムのコンパイル
RUN gcc server.c -o modbus_server `pkg-config --cflags --libs libmodbus`

# Modbus TCPのデフォルト待機ポートを公開
EXPOSE 502

# 実行
CMD ["./modbus_server"]
