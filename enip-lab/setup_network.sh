#!/bin/bash

echo "=== ホストOS用のMacvlanブリッジとルートを設定します ==="
sudo ip link add macvlan-br link enp0s3 type macvlan mode bridge || true
sudo ip addr add 10.7.1.39/32 dev macvlan-br || true
sudo ip link set macvlan-br up || true
sudo ip route add 10.7.1.37/32 dev macvlan-br || true
sudo ip route add 10.7.1.38/32 dev macvlan-br || true
echo "=== ネットワーク設定完了 ==="
