# AIエージェントを活用したKali Linux診断環境セットアップ手順書（Windows / VirtualBox）

本書では、AIエージェントとして「Google Antigravity」を活用し、隔離環境（ローカルネットワーク圏内）でKali Linuxによる自動診断を実現するためのインフラ環境構築手順を解説する。
Windows 11ホストを経由したProxy（プロキシ）通信の確保から、VirtualBox上のKali Linuxと被害想定サーバー（やられサーバー）を安全につなぐネットワークルーティングまで、一連のセットアップをまとめる。

---

## 0. VirtualBoxおよびKali Linuxマシンの事前準備

VirtualBoxへKali Linuxをインポートし、ネットワークの構成いｐを行う。以下は、Windowsホスト側（PowerShell）の操作と、Kali Linux内（ターミナル）の操作を含む。

1. **Kali Linuxの読み込み（インポート）**
   ダウンロードしたKali Linuxのイメージ（`kali-linux-2025.4-virtualbox-amd64`）をVirtualBoxに読み込む。GUIからの追加・インポート、または以下のコマンド例を使用する。
   ```powershell
   VBoxManage import "C:\Users\seched\Downloads\kali-linux-2025.4-virtualbox-amd64.ova"
   ```

2. **内部ネットワーク(intnet7.0)とDHCPサーバーの作成**
   `10.7.0.128` から（`10.7.0.191` まで）のアドレスをDHCPで割り当てる内部ネットワーク（`intnet7.0`）を作成する。
   ```powershell
   .\VBoxManage dhcpserver add --netname intnet7.0 --ip 10.7.0.2 --netmask 255.255.255.0 --lowerip 10.7.0.128 --upperip 10.7.0.191 --enable
   ```

3. **Kali Linuxのアダプタ設定（GUIでの実施）**
   VirtualBoxのGUIからアダプタを割り当てる。
   1. VirtualBoxのメイン画面で対象のVM（例:`kali-linux-2025.4-virtualbox-amd64`）を選択し、「設定」>「ネットワーク」を開く。
   2. **「アダプター 1」**タブを開き、「ネットワークアダプターを有効化」にチェックを入れる。
      - **割り当て:** `内部ネットワーク`
      - **名前:** `intnet7.0`
   3. **「アダプター 2」**のタブを開き、「ネットワークアダプターを有効化」にチェックを入れる。
      - **割り当て:** `ホストオンリーアダプター`
      - **名前:** `VirtualBox Host-Only Ethernet Adapter`（※自分の環境にある名前に合わせる）
   4. 「OK」を押して保存する。

4. **VirtualBox側でのホストオンリーアダプタのIPアドレス設定 (192.168.56.1)**
   デフォルトで `192.168.56.x` と異なるセグメント（例: `192.168.57.x`）が割り当てられている場合は、VirtualBox側の設定を変更してIPを固定する。
   1. VirtualBoxのメイン画面を開く。
   2. メニューバーの「ファイル」 > 「ツール」 > 「Network Manager（ホストネットワークマネージャー）」を開く。
   3. 対象のホストオンリーアダプタ（例: `VirtualBox Host-Only Ethernet Adapter`）を選択する。
   4. 下部の「アダプター」タブで以下の通り変更して「適用」をクリックする。
      - IPv4アドレス: `192.168.56.1`
      - IPv4ネットマスク: `255.255.255.0`

5. **Kali Linux内での静的IPアドレスの設定**
   仮想マシンを起動後、Kali Linux内でそれぞれのインターフェースのIPアドレスをNetworkManagerを用いて静的に設定する。NetworkManager(`nmcli`)を使用する。

   各インターフェース（OS認識名）と、対応するVirtualBoxのアダプタ割り当ては以下の通り：
   - **第1インターフェース** (アダプタ 1 / 内部ネットワーク) : `10.7.0.3` (例 `eth0`)
   - **第2インターフェース** (アダプタ 2 / ホストオンリーアダプタ) : `192.168.56.7` (例 `eth1`)

   ```bash
   # Kali Linuxのターミナルで実行
   
   まず、以下のコマンドで現在のインターフェース名とNetworkManagerの接続名を確認する。
   ```bash
   # インターフェース名（eth0, eth1 等）とアサインされているIPアドレスの確認
   ip addr show

   # インターフェース名に対応する接続名（Wired connection 1 等）の確認
   nmcli connection show
   ```

   # 第1インターフェースへのIP設定
   sudo nmcli connection modify "Wired connection 1" ifname eth0 ipv4.method manual ipv4.addresses 10.7.0.3/24
   sudo nmcli connection up "Wired connection 1"
   
   # 第2インターフェースへのIP設定（新規接続プロファイル作成）
   # 上記手順4で VirtualBox側に 192.168.56.1/24 を設定した通信可能なセグメント(192.168.56.7) にする。
   sudo nmcli connection add type ethernet ifname eth1 con-name "eth1-static" ipv4.method manual ipv4.addresses 192.168.56.7/24
   sudo nmcli connection up "eth1-static"
   ```

6. **sshの起動時の自動起動化、起動、状態の確認**
   Kali Linux内でSSHサーバーを起動し、さらにOS起動時に自動で立ち上がるように設定する。これにより、次回以降のVM起動時には自動的にSSHが有効になる。
   ```bash
   # 自動起動を有効化
   sudo systemctl enable ssh
   # サービスを起動
   sudo systemctl start ssh
   # 状態の確認
   sudo systemctl status ssh
   ```

7. **Kali Linuxのタイムゾーン設定（Asia/Tokyo）**
ログのタイムスタンプを日本時間（JST）に合わせるため、タイムゾーンを `Asia/Tokyo` に変更する。
   ```bash
   sudo timedatectl set-timezone Asia/Tokyo
   ```

## 1. WSL (Windows Subsystem for Linux) と Ubuntu のインストール
Windows上でProxyを動作させる軽量なLinux環境を準備する。

1. **WSLの有効化とインストール**
   管理者PowerShellを開き、以下のコマンドを実行後、PCを再起動する。
   ```powershell
   wsl --install
   ```

2. **Ubuntuディストリビューションのインストールと初期設定**
   再起動後、PowerShellで以下のコマンドを実行しUbuntuをダウンロード・インストールする。
   ```powershell
   wsl --install -d Ubuntu
   ```
   インストール直後に新しいUNIXユーザーの作成画面が表示されたため、ユーザー名とパスワード（例: `kali`）を設定する。

---

## 2. WSL上のProxyサーバー（TinyProxy）の構築
Kali Linuxからの通信を中継するための軽量ProxyサーバーをUbuntu内に構築する。

1. **TinyProxyのインストール**
   WSL上のUbuntuに入り、パッケージを更新してインストールを行う。
   ```bash
   sudo apt-get update
   sudo apt-get install -y tinyproxy
   ```

2. **TinyProxyのアクセス許可設定 (`/etc/tinyproxy/tinyproxy.conf`)**
   VirtualBoxのホストオンリーネットワーク（`192.168.56.0/24`）と、WSL自身のネットワーク（`172.16.0.0/12`）からの通信を許可するように設定ファイルを書き換える。具体的には、`Allow 127.0.0.1` の行をコメントアウトし、`Allow 192.168.56.0/24` と `Allow 172.16.0.0/12` の行を追加する。
   ```bash
   sudo sed -i 's/^Allow 127.0.0.1/#Allow 127.0.0.1\nAllow 192.168.56.0\/24\nAllow 172.16.0.0\/12/' /etc/tinyproxy/tinyproxy.conf
   ```

3. **TinyProxyサービスの起動**
   設定の変更を反映させるためサービスを再起動する。
   ```bash
   sudo service tinyproxy restart
   ```

---

## 3. Windows 11側のポートフォワーディング設定
VirtualBoxのネットワーク（Kali）から送られてきたプロキシ通信を、WSL内のTinyProxyへ転送するための紐づけ（ポートプロキシ）を行う。

1. **WSLネットワークのIPアドレスの確認**
   WSLのIPは変動するため、現在のIPアドレスを取得する（今回は `172.26.201.248`）。
   ```bash
   # Ubuntu内で確認する場合のコマンド
   ip addr show eth0
   ```

2. **管理者PowerShellでのプロキシ転送ルールの追加**
   （※必ず管理者PowerShellで実施）
   ホストオンリーアダプタのIP（`192.168.56.1`）のポート`8888`への通信を、WSLのIPのポート`8888`へ転送するルールを登録する。
   さらに、後述のAntigravityのバックエンド（GOモジュール）が直接HTTPS（ポート`443`）で通信しようとするバグを回避するため、ポート`443`に来た通信は**プロキシを通さず直接GoogleのAPIサーバー（daily-cloudcode-pa.googleapis.com）へ転送する**ルールを追加する。
   ```powershell
   # 8888ポートの転送
   netsh interface portproxy add v4tov4 listenport=8888 listenaddress=192.168.56.1 connectport=8888 connectaddress=172.26.201.248
   
   # 443ポート通信をGoogleのAPIサーバーへ直接転送
   netsh interface portproxy add v4tov4 listenport=443 listenaddress=192.168.56.1 connectport=443 connectaddress="daily-cloudcode-pa.googleapis.com"
   ```


---

## 4. Windowsのファイアウォール・ルーティング設定
ポートフォワーディングしたネットワークトラフィックがWindows内で遮断されないように、各種セキュリティ許可を行う。

1. **Windows Defender ファイアウォールの受信許可 (ポート 8888, 443)**
   管理者PowerShellで、ProxyおよびHTTPS用のポートを開放する。
   ```powershell
   # 8888ポート
   netsh advfirewall firewall add rule name="WSL Proxy Port 8888" dir=in action=allow protocol=TCP localport=8888
   # 443ポート
   netsh advfirewall firewall add rule name="WSL Proxy Port 443" dir=in action=allow protocol=TCP localport=443
   ```

2. **VirtualBox Host-OnlyアダプタのIPフォワーディング有効化**
   ホストオンリーネットワークから別のネットワーク（WSL）への「中継（ルーティング）」を許可する。
   ```powershell
   # 管理者PowerShell
   Get-NetAdapter | Where-Object { $_.InterfaceDescription -like '*VirtualBox Host-Only*' } | Get-NetIPInterface | Set-NetIPInterface -Forwarding Enabled
   ```

---

## 5. WSL (Ubuntu) セッションの維持（サスペンド防止）

WSLのUbuntuは、バックグラウンドでのアクティブなプロセスがないと一定時間後に不要と判断され、サスペンド（停止）してしまい、TinyProxyの通信が途絶える場合がある。
これを防ぐため、Ubuntuのターミナルを起動したまま以下のコマンドを実行し、TinyProxyのアクセスログを監視し続ける（セッションを維持する）ことを推奨する。

```bash
# Ubuntuのターミナルで実行してウィンドウはそのまま開いておく
sudo tail -f /var/log/tinyproxy/tinyproxy.log
```

---

## 6. Antigravityのリモートウィンドウ実行のための事前確認

VS Codeで「リモートウィンドウ」を開きAntigravityを稼働させる前に、Windowsのコマンドプロンプト（cmd）からKali LinuxへのSSH接続テストを行う。

1. **VS Code（Antigravity）用 SSH設定の追加**
   VS Codeのリモート接続時にわかりやすいホスト名（`KaliLinux`）で接続できるように、SSHの設定ファイル（`C:\Users\yoned\.ssh\config`）に構成を追加する。
   - `C:\Users\yoned\.ssh\config` を開く。（存在しない場合は新規作成する）
   - ファイルの末尾に以下の内容を追記して保存する。
     ```text
     Host KaliLinux
         HostName 192.168.56.7
         User kali
     ```

2. **コマンドプロンプトからの接続テスト**
   コマンドプロンプトを起動し、以下のコマンドで接続を試みる（IPアドレスの代わりに上記で設定したホスト名を使用）。
   ```cmd
   ssh -v KaliLinux
   ```

   > [!NOTE] 
   > **【トラブルシューティング1】**
   > 確認時、もし `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!` という警告文が出た場合は、末尾の「[8. トラブルシューティング：2. SSH接続時に鍵情報が競合するエラーが出た場合](#2-ssh接続時に鍵情報が競合するエラーが出た場合)」を参照し、対処を行ってから再度実行してください。

3. **ログインの確認**
   初回ログイン時、`Are you sure you want to continue connecting (yes/no/[fingerprint])?` と聞かれたら `yes` と入力します。パスワード（初期値はkali）を入力後、正常にログインできることを確認します。確認後、`exit` でログアウトします。

4. **初回リモート接続とモジュールの一括ダウンロード（NAT利用）**
   VS Code（Antigravity）がKali Linuxへ初回接続する際、サーバープログラムや拡張機能をインターネットからダウンロードしようとする。プロキシだけでは通信エラーやタイムアウトが発生する可能性があるため、本格的な作業を開始する前に一時的にNATを利用してモジュールをダウンロードさせる。
   - VirtualBoxマネージャー上でKali Linuxを一度**シャットダウン**する。
   - Kali Linuxの「設定」画面を開き、ネットワークの**「アダプター3」に「NAT」**を割り当てて有効化する。
   - Kali Linuxを起動する。（これでKaliは一時的に直接インターネットに接続できる状態になる）
   - VS Codeのコマンドパレット（`Ctrl+Shift+P`）等から「Connect to SSH host...」を選択し、ドロップダウンから `KaliLinux` を選択してリモート接続を行う。
   - リモートウィンドウが開き、SSHのパスワード入力後、Open folderで、`/home/kali`を選択し、再度パスワード入力後、チャットの応答が返ってくることを確認する
   - 確認できたら、Kali Linuxを再度シャットダウンし、**「アダプター3（NAT）」のチェックを外して無効化**し、元の隔離に戻す。

---

## 7. Kali LinuxでのHTTP Proxy設定

### 1. `/etc/hosts` へのエントリ追加（Antigravityのバックエンド用回避策）
本来AntigravityのHTTP Proxy設定のみで対応できるが、Antigravityのバックエンド（GOモジュール）にHTTP Proxy関連の環境変数を読まない、というバグがある。そこで、
`/etc/hosts`に、以下を追加する。

```text
# Kali LinuxやUbuntu上で動作するAntigravityのバックエンド（GOモジュール）が
# HTTP Proxy環境変数を無視して直接通信を試みるバグを回避するため、
# プロキシサーバーが稼働しているホストOS側のIP（192.168.56.1）に
# 強制的に名前解決させ、通信を中継させる。
192.168.56.1  daily-cloudcode-pa.googleapis.com
192.168.56.1  cloudcode-pa.googleapis.com
192.168.56.1  play.googleapis.com
192.168.56.1  www.googleapis.com
```

上記のホストはAntigravityのバックエンド（GOモジュール）が環境変数のProxy指定を無視して、直接インターネットアクセスを試みてしまう通信先です。
各ドメインの設定理由は以下の通りです。

- **`daily-cloudcode-pa.googleapis.com` / `cloudcode-pa.googleapis.com`**:
 これらを設定しないと、AntigravityのコアAPIに到達できず、**チャットなどのやり取り自体が一切できなくなります（必須）**。
- **`play.googleapis.com` / `www.googleapis.com`**:
  これらを設定しないと、チャット等の基本機能は動きますが、バックグラウンドでの定期的な情報提供（利用ログ等）の通信がブロックされるため、**VS CodeのOutput（Antigravity）に「Connection refused」等の通信エラーが大量に出力され続けてしまいます**。エラーのスパムを防ぐために併せて設定します。

`/etc/hosts` にて、これらを `192.168.56.1` に強制的に名前解決させることで、ホストOS（Windows）側に設定した**ポートフォワーディング機能（`netsh interface portproxy` による転送設定）**を利用し、TinyProxyを通さずに一括して直接外部（Google APIサーバー）へ通信を転送させる(バグが治るまでの例外的な処理)。

### 2. AntigravityのRemote settingのHTTP Proxy設定
Antigravityで、Open a Remote Window(左下の><マーク>)をクリックし、Connect to a SSH Host...を選択しKaliLinuxを選択する。
リモートウィンドウが立ち上がったら、
VS Codeのリモート（`KaliLinux`）ウィンドウ上で、Antigravityがプロキシを経由して通信できるように設定を行う。
VS Codeの設定（Settings）を、File->Preferences->Edirot Settingsを開き、上部の検索窓でproxyと入力し、「Remote [SSH:KaliLinux]」のタブ内で以下の項目を設定・変更する。

- **HTTP Proxy** -> `http://192.168.56.1:8888`
- **Strict SSL Proxy** -> `OFF`
- **Server Certificates** -> `OFF`

> **※ 補足**
> 上記の「Strict SSL Proxy」および「Server Certificates」を `OFF` にする詳細な理由については、末尾の「[9. 補足：2. AntigravityのRemote settingのHTTP Proxy設定にて、Strict SSL Proxy/Server CertificatesをOFFにする理由](#2-antigravityのremote-settingのhttp-proxy設定にてstrict-ssl-proxyserver-certificatesをoffにする理由)」をご参照ください。

### 3. 設定の確実な適用と完全な隔離環境での再起動
VS Codeのリモート設定で変更した内容は、バックグラウンドのプロセスに即座に反映されない場合がある。
新しいプロキシ設定を確実にAntigravityのモジュールへ適用させ、かつ純粋な「隔離環境（NATなし・Proxyのみ）」で通信できる状態へ移行するため、以下の手順を実施する。

1. プロキシ設定の入力が完了したら、作業しているVS Codeの「リモートウィンドウ」を一度すべて閉じる。
2. Kali Linux上で電源オフまたは `sudo shutdown -h now` 等を実行し、システムを**シャットダウン**する。
3. VirtualBoxマネージャーでKali Linuxの「設定」画面を開き、ネットワークの**「アダプター3（NAT）」の無効化（チェックを外す）**を行い、本番の隔離設定に戻す。
4. Kali Linuxを再度起動する。
5. VS Codeから「Connect to SSH host...」で `KaliLinux` へつなぎ直す。これで新しいプロキシ設定が完全に反映され、隔離された環境下でもチャットや拡張機能が正常に機能する状態となる。

### 4. Kali Linux上のAntigravityの作業フォルダの作成

1. Kali Linux上で、/home/kali/loalwork/vulerability_test（任意)等の名前の作業フォルダを作成する。
2. AntigravityのリモートウィンドウのOpen folderで上記フォルダを選択する。
3.  一通り作業が終わったら、Save Workspace as..を選択し、workspaceファイルを作業フォルダに保存する（記憶と知識がworkspaceに保存される）。


### 5. 動作確認（Metasploitable2への診断指示）

構築した環境（Proxy経由のAI通信と、VirtualBoxのローカルネットワーク通信）が正しく連動して動作しているか確認するため、やられサーバー（Metasploitable2）を内部ネットワークに接続し、VS Code上のAntigravity（AIチャット）からKali Linuxにスキャン・診断を自動実行させます。

#### 1. Metasploitable2のネットワーク設定と起動
1. VirtualBoxマネージャーを開き、インポート済みの `metasploitable2` 仮想マシンの「設定」を開く。
2. 「ネットワーク」>「アダプター 1」を開き、以下のように設定して保存する。
   - **割り当て:** `内部ネットワーク`
   - **名前:** `intnet7.0`
3. `metasploitable2` 仮想マシンを起動する。
4. ログイン画面が出たら、ユーザー名 `msfadmin` / パスワード `msfadmin` でログインする。
5. コンソールで `ip a` または `ifconfig` を実行し、割り当てられたIPv4アドレスを確認する。
   （※ 例: `10.7.0.128` など、設定したDHCPの範囲のIPが割り当てられていることを確認する。）

#### 2. VS Code（Kali Linux側）からのAI診断
1. プロキシ設定を完了させたVS Codeから `KaliLinux` へ**リモート接続**（SSH）を行い、Antigravity（チャットウィンドウ）を開く。
2. チャットの入力欄で、先ほど確認したMetasploitable2のIPアドレスを指定し、以下のようなプロンプトを入力して指示を出す。

   **【指示の例】**
   > `内部ネットワークにある 10.7.0.xxx （※確認したIPアドレス）に対して、nmapを用いて主要なポートのスキャンを実行し、稼働しているサービスや脆弱性の可能性がある箇所を診断してください。`

3. AI（Antigravity）がKali Linux内で自動的に `nmap` コマンド等を実行し、その結果をもとに診断レポートをチャット上で回答してくることを確認する。

ここでAIが正常に思考し、裏側でスキャンを実行して解説を返してくれば、**プロキシ越しのAI通信（インターネット側）** と **内部ネットワーク間のスキャン通信（ローカル側）** を含めたすべてのインフラ構築が成功しています。





---

## 8. トラブルシューティング

### 1. リモートウィンドウでのチャット応答がGenerating...のまま止まる時は

OutputのAntigravity（またはバックエンドのGOモジュール側のログ）にて、以下のような「Connection refused」メッセージが出力され、チャットなどAIとの通信が止まってしまうことがあります。

**【原因と対処】**
`daily-cloudcode-pa.googleapis.com` 等のGoogleのAPIサーバーのIPアドレスが変動したことにより、Windowsに登録していたポートプロキシ（`netsh interface portproxy`）の転送先・転送経路に不整合が生じていることが原因です。
これを直すには、管理者PowerShellで `iphlpsvc` サービスを再起動し、ポート転送の設定を強制的にリフレッシュする必要があります。

```powershell
# ポート転送の設定を強制リフレッシュ
Restart-Service iphlpsvc
```

**参考：該当するエラーメッセージの例**
```text
026-03-24 10:20:26.617 [info] W0324 10:20:26.616773 13910 log_context.go:118] Failed to refresh cache in background: failed to get load code assist response: Post "https://daily-cloudcode-pa.googleapis.com/v1internal:loadCodeAssist": dial tcp 192.168.56.1:443: connect: connection refused
```

### 2. SSH接続時に鍵情報が競合するエラーが出た場合

本エラーは、「**6. Antigravityのリモートウィンドウ実行のための事前確認**」における手順2「**コマンドプロンプトからの接続テスト**」の段階で発生しうるトラブルです。

**【原因と対処】**
過去に同じIPアドレス（またはホスト名）の環境に接続したことがあり、仮想マシンを再インポート・再構築したことでサーバー側の鍵情報が変わってしまったことが原因です。
以下のような警告文が出ます。

```text
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
```

ログの中に `Offending ECDSA key in C:\Users\seched/known_hosts:26` のようなメッセージが表示されるため、以下の手順で指定された行（この例では26行目）を削除して接続履歴をリセットします。

1. メモ帳やVS Codeなどで `C:\Users\seched\.ssh\known_hosts` を開く。
2. 該当する行（`192.168.56.7` や `KaliLinux` から始まる行）を丸ごと削除し、上書き保存する。
3. 再度 `ssh -v KaliLinux` などを実行して接続をテストする。

### 3. Windowsファイアウォールを一旦無効化し、既定の設定に戻した場合の復旧手順

Windowsのファイアウォールをトラブルシューティング等の目的で無効化し、その後「既定の設定に戻す」を実行した場合、本書の「4. Windowsのファイアウォール・ルーティング設定」で手動追加したファイアウォールの受信許可ルールが消去されてしまいます。その結果、プロキシ通信（8888番）やGoogle APIへのSSL通信（443番）が遮断され、Antigravity（リモートウィンドウ）が正常に機能しなくなります。(ポートプロキシ設定およびIP転送設定は影響受けず)

以下に、設定の消失を確認する手順と、再設定する手順を記載します。

#### 1. 設定が消去されていること（ルールの消失）の確認

管理者PowerShellを開き、以下のコマンドを実行して追加したルールが存在するか確認します。

```powershell
# 8888ポートルールの確認
netsh advfirewall firewall show rule name="WSL Proxy Port 8888"

# 443ポートルールの確認
netsh advfirewall firewall show rule name="WSL Proxy Port 443"
```

**確認結果:**
「指定された条件に一致する規則がない」という旨のメッセージが表示された場合、ルールが消失しているため再設定が必要です。（ルールの詳細が表示された場合は正常に存在しています）

#### 2. 再び設定する手順

ルールが消失していた場合は、再びルールを追加します。
必ず**管理者PowerShell**を開き、以下のコマンドを実行して設定を復旧させてください。

```powershell
# 8888ポート用の受信許可ルールの再追加
netsh advfirewall firewall add rule name="WSL Proxy Port 8888" dir=in action=allow protocol=TCP localport=8888

# 443ポート用の受信許可ルールの再追加
netsh advfirewall firewall add rule name="WSL Proxy Port 443" dir=in action=allow protocol=TCP localport=443
```

### 4. Kali Linuxへのリモート接続時にVS Code Serverのダウンロードエラーが発生した場合

VS Codeのバージョンアップ等により、Windows側のVS Codeクライアントのバージョンが変わると、Kali Linux仮想マシン内にそれに合致する新しい「VS Code Server」が必要になります。
しかし、VS Codeは初期のダウンロードフェーズで自動的にプロキシを通すことができず、ログ（Outputタブ等）に `Error downloading server from all URLs` や `installation failed` というエラーを出して接続処理が止まってしまうことがあります。

このエラーが発生した場合は、以下の手順で一時的にKaliマシンのNATを有効化して直接ダウンロード通信を許可することで解決します。

1. **Kali Linuxのシャットダウン**
   現在起動しているKali LinuxをVirtualBoxマネージャー上、またはターミナルから一旦シャットダウンします。
2. **NATアダプタの一時有効化**
   VirtualBoxマネージャー上でKali Linuxの「設定」画面を開き、ネットワークの **「アダプター3」に割り当てた「NAT」を割り当てて有効化** します。(未割当の場合は新規に割り当てる)
3. **Kali Linuxの起動とVS Codeからの再接続**
   Kali Linuxを起動した後、VS Codeから再度 `KaliLinux` へリモートウィンドウを開いてSSH接続を行います。パスワードを入力後、バックグランドでVS Code ServerがNAT接続経由でダウンロードされる。
4. **接続および動作の確認**
   VS Codeの画面左下にSSH:KaliLinuxと表示され、エクスプローラー（Open Folder 等）が表示されて正常にリモート接続が確立されたことを確認する。
5. **NATアダプタの無効化（隔離環境へ戻す）**
   確認ができたら、再度Kali Linuxをシャットダウンし、**「アダプター3（NAT）」のチェックを外して無効化** する。その後起動すれば、元のクローズドなプロキシ経由の環境に戻る。

---

## 9. 補足

### 1. Kali Linuxの接続される内部ネットワークを変更した場合の対応手順

例として、内部ネットワークを `intnet13` から `intnet7.0` に変更し、Kali LinuxのIPアドレスを `192.168.13.140` から `10.7.0.3` に変更する場合、以下の設定変更が必要になります。

#### 【Kali Linux 立ち上げ前に実施する手順 (Windowsホスト側)】

1. **新しいDHCPサーバーの作成**
   PowerShell等で以下のコマンドを使用して、新しい内部ネットワーク用のDHCPサーバーを作成します。
   ```powershell
   .\VBoxManage dhcpserver add --netname intnet7.0 --ip 10.7.0.2 --netmask 255.255.255.0 --lowerip 10.7.0.128 --upperip 10.7.0.191 --enable
   ```
2. **VirtualBoxのアダプタ割り当て変更**
   VirtualBoxのメイン画面から対象のKali Linuxマシンの「設定」>「ネットワーク」を開き、「アダプター 1」の「名前」を新しい内部ネットワーク（例: `intnet7.0`）に変更して「OK」で保存します。

#### 【Kali Linux 立ち上げ後に実施する手順 (Kali Linux内)】

1. **Kali Linux内での静的IPアドレスの変更**
   Kali Linuxを起動し、ターミナルを開いてから第1インターフェース（内部ネットワーク側）のIPアドレスを新しいセグメントのものに変更し、適用します。
   ```bash
   # 第1インターフェースのIPアドレスを変更
   sudo nmcli connection modify "Wired connection 1" ipv4.addresses 10.7.0.3/24
   # 接続を再起動して設定を適用
   sudo nmcli connection up "Wired connection 1"
   ```
   ※ `/etc/network/interfaces` を利用して設定している場合は、ファイル内の該当する `address` を `10.7.0.3` に書き換えた後、OSを再起動するかネットワークサービスを再起動（`sudo systemctl restart networking`）して反映させます。

*(補足)*
内部ネットワーク（アダプター 1）の設定変更のみであれば、ホストオンリーアダプタ側（アダプター 2の `192.168.56.x`）は変わらないため、Windows側のポートフォワーディングやVS CodeのHTTP Proxy設定などは今まで通りのままで問題ありません。

### 2. AntigravityのRemote settingのHTTP Proxy設定にて、Strict SSL Proxy/Server CertificatesをOFFにする理由

プロキシサーバー（今回はWSL上のTinyProxy）を経由して外部とHTTPS通信を行う際、プロキシ自体の証明書や、接続先（Google APIなど）のサーバー証明書の検証フェーズ（TLSハンドシェイク）でエラーとなり、Antigravityの通信が遮断されてしまうケース（チャットがGeneratingから進まない等）があります。

今回は検証用のクローズドなローカルプロキシ環境であることを前提としているため、**「Strict SSL Proxy」をOFFにしてプロキシ経由時のSSL検証を無効化**し、さらに**「Server Certificates」もOFFにして接続先サーバーの証明書エラーも許容させる**ことで、二段構えで通信エラーを完全に回避させています。
