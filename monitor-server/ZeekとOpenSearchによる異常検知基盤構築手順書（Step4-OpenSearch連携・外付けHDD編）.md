# Zeek と OpenSearch による 異常検知基盤構築手順書(Step4:OpenSearch連携・外付けHDD編)

> [!CAUTION]
> **【重要】OpenSearchスタック起動時の運用ルール（ディスク枯渇防止）**
> 本環境では、ログの長期保存のためにOpenSearchのデータを外付けHDDに保存する構成としている。
> HDDを接続しないまま `docker-compose up` を実行すると、マウントエラーにならずに**VMのローカルディスク側に新規データベースを作成してしまい、VMの容量が瞬時に枯渇してシステムがクラッシュする危険**がある。
> そのため、OpenSearchスタックを起動する際は、**「必ず外付けHDDを接続し、`df -h /opt/opensearch_data` コマンドで容量（1TB等）が正しく認識されていることを確認してから起動コマンドを打つ」** ことを運用ルールとして徹底する。

USB接続のHDDを外付けで接続し、VirtualBox上のKali / UbuntuゲストOSに認識させ、OpenSearchがその大容量ディスク専用にデータを保存するように構成変更する手順を記載する。
この手順では、**「新しい外付けHDD自体を、OpenSearchのデータ保存先（ `/opt/opensearch_data` ）としてマウント（割り当て）する」** 安全かつ確実な方式をとる。

---
## 事前準備
USBの外付けHDDをゲストOSに認識させるためにVirtualBoxに適切にExtensionPackがインストールされ、さらにゲストOSにGestAddtionToolBoxがインストールされている必要がある。その確認の手順を示す。

1. VirtualBoxのバージョンを確認し、「ファイル」 > 「ツール」 > 「拡張機能」で表示されるExtensionPackのバージョンと一致することを確認する。
2. 一致しなければ同一バージョンのExtensionPackをインストールする。
3. VirtualBoxを再起動する。
4. ゲストOSを起動し、GestAddtionToolBoxをインストールする。
5. ゲストOSをシャットダウンする。

## 第1段階：ホストOS（Windows）とVirtualBoxの設定

まず、物理的なHDDをVirtualBox経由でゲストOSにパススルー（直接接続）する。

1. **HDDの物理接続**: 1TBの外付けHDDをホストPC（Windows等）のUSBポートに挿 入する。
2. **VMの停止**: 一度、稼働中の `MonitorServer`（ゲストOS）をシャットダウンする。
3. **USB設定**: VirtualBoxマネージャーの画面で `MonitorServer` を選択し、「設定」>「USB」を開く。
4. **コントローラーの有効化**: 「USBコントローラーを有効化」にチェックを入れる。USB 1,2,3の選択はできずすべて有効となる。
5. **デバイスの追加**: 画面右側の `+`（プラスアイコン）をクリックし、表示されたリストから接続した1TBのHDDを選択する。（※リストにチェックが入る）
今回の例では、JMicron USB to ATA/ATAPI Bridge[0601]
6. 「OK」を押して設定を保存。
7. モバイルUSB HDDを一旦抜く。抜かないとホストOS Windows11が握って離さない場合がある。
8. ゲストOSを**起動**する。
9. モバイルUSB HDDを指す。
10. ゲストOSのデバイス->USB で、先ほど追加したUSBデバイスにチェックが入っていることを確認する。
---

## 第2段階：ゲストOS（Linux）側でのディスク準備

ゲストOSがHDDを認識しているか確認し、Linux向けのファイルシステム（`ext4`）でフォーマットする。
> [!WARNING]
> 以下のフォーマット手順を実施すると、新品ではなく既存のデータが入っていた場合、**外付けHDDの中身がすべて消去**されます。大事なデータが入っていない専用の空HDDを用意すること。

**1. デバイス名の確認**
ターミナルで以下のコマンドを実行する。
```bash
lsblk
```
実行結果例：
```text
NAME                      MAJ:MIN RM   SIZE RO TYPE MOUNTPOINTS
loop0                       7:0    0  63.9M  1 loop /snap/core20/2318
loop1                       7:1    0  63.8M  1 loop /snap/core20/2769
loop2                       7:2    0  91.7M  1 loop /snap/lxd/38469
loop3                       7:3    0  91.7M  1 loop /snap/lxd/38800
loop4                       7:4    0  38.8M  1 loop /snap/snapd/21759
loop5                       7:5    0  48.4M  1 loop /snap/snapd/26382
sda                         8:0    0  48.8G  0 disk
├─sda1                      8:1    0     1M  0 part
├─sda2                      8:2    0     2G  0 part /boot
└─sda3                      8:3    0  46.8G  0 part
  └─ubuntu--vg-ubuntu--lv 252:0    0  23.4G  0 lvm  /
sdb                         8:16   0 931.5G  0 disk
└─sdb1                      8:17   0 931.5G  0 part
sr0                        11:0    1    51M  0 rom
```
通常、元からあるOSディスクが `sda`、今回新しく追加した外付けHDDが `sdb` として見える。容量（931.5G / 1T 等）を頼りにターゲットを見つける。上記の場合、`sdb` の下に `sdb1` というパーティションが作成されている。（ここでは例として対象パーティションを `/dev/sdb1` とする。自身の環境に合わせて読み替える）

**2. パーティションのフォーマット**
Linuxで最も安定している `ext4` 形式でパーティション（`sdb1`）をフォーマットする。
```bash
# パーティションをext4形式でフォーマット
sudo mkfs.ext4 /dev/sdb1
```
*(※尋ねられたら `y` で進む。完了まで数秒〜数分かかる)*

---

## 第3段階：OpenSearchデータの移行とマウント設定

現在溜まっているOpenSearchのデータを失わずに、新しいHDDへ移し替える。

**1. OpenSearchコンテナの停止**
データ移行中の書き込みを防ぐため、Dockerコンテナ群を完全に停止させる。
```bash
cd /home/kali/localwork/opensearch_stack
sudo docker-compose down
```

**2. 新規ディレクトリの作成と一時マウント・データ移行**
ホストOS側に新しいHDDをマウントするためのディレクトリ（`/opt/opensearch_data`）を作成し、一時マウントやデータ移行を行う。

> **【重要】OpenSearch Dashboardsの設定や過去ログを引き継ぐ場合は移行が必須**
> OpenSearch DashboardsのDiscover（Data View）やVisualize Libraryの設定は、すべてOpenSearchのデータベース内に保存されている。これまで仮想ディスク上で作成した画面設定や過去のログデータを引き続き活用する場合は、**ここで必ず古いボリュームから新しい外付けHDDへデータをコピーすること**。移行せずに進めるとOpenSearch Dashboardsは初期画面に戻る。

```bash
# ホスト側にマウント先ディレクトリを作成
sudo mkdir -p /opt/opensearch_data

# 新しいHDDを一時マウント
sudo mount /dev/sdb1 /mnt

# 古いDockerボリュームの存在を確認する
sudo ls -l /var/lib/docker/volumes/

# Step3で名前付きボリューム「es_data」を設定しているため、以下の固定パスからデータを丸ごとコピーする
sudo rsync -avP /var/lib/docker/volumes/opensearch_stack_es_data/_data/ /mnt/

# 作業が終わったら一時マウント解除
sudo umount /mnt
```

**3. HDDのUUID（一意の識別番号）を確認**
USBの抜き差しなどで `/dev/sdb1` という名前が変わっても確実にマウントできるように、UUIDを調べる必要がある。
```bash
sudo blkid /dev/sdb1
```


出力結果から `UUID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"` の部分をメモまたはコピーする。

出力結果が、
┌──(kali㉿10.7.1.32:MonitorServer)-[~/localwork/opensearch_stack]
└─$ sudo blkid /dev/sdb1
/dev/sdb1: UUID="04aadd5a-693e-495b-9ef2-cbeae9a6605c" BLOCK_SIZE="4096" TYPE="ext4" PARTUUID="7da4ba0c-01"
の場合は、`UUID="04aadd5a-693e-495b-9ef2-cbeae9a6605c"` の部分をコピーする。

**4. 永続マウント設定（fstabの編集）**
OS再起動時にも自動的に `/opt/opensearch_data` として割り当てられるようにする。
1. `fstab` ファイルをエディタで開く。
   ```bash
   sudo nano /etc/fstab
   ```
2. ファイルの末尾に以下の1行を追記する。（`UUID=...` は先ほど調べたものに書き換える）
   ```text
   UUID=ここにコピーしたUUIDを貼る  /opt/opensearch_data  ext4  defaults,nofail  0  2
   ```
   ※注：`nofail`を入れないと、指定したHDDがUSB接続されていない場合ゲストOSが起動すらしないため。一方、指定したHDDがUSB接続されていないと、Elastic Searchは動作しないので、**3. OpenSearchスタックの起動** にて、指定したHDDがUSB接続されていることを確認するコマンドとしている。
3. 保存（`Ctrl+O`, `Enter`, `Ctrl+X`）して終了する。


**5. テストマウントと権限の再適用**
`fstab` を編集した後は、まず変更内容をOSに再読み込みさせる。
```bash
sudo systemctl daemon-reload
```

次に、設定した `fstab` を元にシステムにマウントさせ、エラーが出ないか確認する。
```bash
sudo mount -a
```
※何もエラーが表示されなければ成功です。正しくマウントされているか `df -h /opt/opensearch_data` で確認し、1TBの容量が表示されれば完璧です。

Docker内のOpenSearch（デフォルトUID: 1000）が書き込めるように所有権を変更する。
```bash
sudo chown -R 1000:1000 /opt/opensearch_data
```

---

## 第4段階：Docker Composeの修正と起動

**1. 設定ファイルのバックアップ取得**

設定を変更する前に、外付けHDDなし版のバックアップファイル（`docker-compose.yml_no_external_HDD.bak`）を作成しておく。

```bash
cd /home/kali/localwork/opensearch_stack
cp docker-compose.yml docker-compose.yml_no_external_HDD.bak
```

**2. docker-compose.yml にマウント設定を追記**

```bash
nano /home/kali/localwork/opensearch_stack/docker-compose.yml
```
`opensearch` の設定項目に `volumes` を追加し、マウントしたHDDを紐付ける。

```yaml
  opensearch:
    image: opensearchproject/opensearch:1.3.14
    container_name: opensearch
    environment:
      - node.name=opensearch-node1
      # ... (中略) ...
    volumes:
      - /opt/opensearch_data:/usr/share/opensearch/data  # ←ここを追記
```

**3. OpenSearchスタックの起動**

※注：起動前に必ず `CheckExternalHDD.sh` を実行して「USB接続のHDDが正しくマウントされているか」を確認する。HDDが未接続の場合はローカルディスクへの誤書き込みを防止するため、後続の `docker-compose up -d` を実行しないこと。

```bash
cd /home/kali/localwork/opensearch_stack
./CheckExternalHDD.sh
sudo docker-compose up -d
```
エラーなく起動し、OpenSearch Dashboardsにもアクセスできるようになればディスク移行は完了。

**4. ISM (Index State Management) による保存期間の拡張**
以前は小容量ディスクのために短い期間でデータが消去される設定だったが、1TBあれば **100日〜半年近く** のデータを余裕で遡って機械学習やフォレンジックにあてることができる。
以下のコマンドを実行して、OpenSearchの `filebeat` 用ポリシーを作成・更新し、データの保存期間を `90 days` に大幅に延長する。

```bash
curl -X PUT "http://localhost:9200/_plugins/_ism/policies/filebeat" -H 'Content-Type: application/json' -d'
{
  "policy": {
    "description": "Log retention policy for Zeek",
    "default_state": "hot",
    "states": [
      {
        "name": "hot",
        "actions": [
          {
            "rollover": {
              "min_index_age": "30d",
              "min_size": "50gb"
            }
          }
        ],
        "transitions": [
          {
            "state_name": "delete",
            "conditions": {
              "min_index_age": "90d"
            }
          }
        ]
      },
      {
        "name": "delete",
        "actions": [
          {
            "delete": {}
          }
        ],
        "transitions": []
      }
    ],
    "ism_template": {
      "index_patterns": ["filebeat-*"],
      "priority": 100
    }
  }
}'
```

---

## 5. 日々の安全なシステム終了・起動手順
外付けHDD環境へ移行後は、データベースの破損を防ぐため、以下の手順でシステムの停止と起動を行うことを強く推奨する。

### 【終了時の手順】
VMをシャットダウンする際は、必ずデータの入り口（Zeek）から順に安全に停止させる。

1. **パケット収集（Zeek）の停止**
   ```bash
   sudo /opt/zeek/bin/zeekctl stop
   ```
2. **OpenSearchコンテナ群の停止**
   ```bash
   cd /home/kali/localwork/opensearch_stack
   sudo docker-compose down
   ```
3. **ゲストOSのシャットダウン**
   ```bash
   sudo shutdown -h now
   ```

### 【起動・再開時の手順】
VM起動後は、外付けHDDの認識を確認した上で、データベース（OpenSearch）から先に起動する。

1. **VM起動後、外付けHDDが認識（マウント）されていることを確認**
   ※ `fstab` で自動マウント設定済みの場合は、起動時点で自動的にマウントされている。
2. **OpenSearchコンテナ群の起動**
   ```bash
   cd /home/kali/localwork/opensearch_stack
   ./CheckExternalHDD.sh
   sudo docker-compose up -d
   ```
   ※事前にスクリプトでマウント状態の安全チェックを行うこと。
3. **パケット収集（Zeek）の再開**
   ```bash
   sudo /opt/zeek/bin/zeekctl start
   ```
   ※もしシグネチャ等の設定変更を行った場合は `start` ではなく `deploy` を使用してください。
