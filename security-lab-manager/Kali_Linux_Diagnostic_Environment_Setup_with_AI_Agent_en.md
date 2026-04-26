# Kali Linux Diagnostic Environment Setup Procedure Using AI Agent (Windows / VirtualBox)

This document describes the infrastructure setup procedures for utilizing "Google Antigravity" as an AI agent to achieve automated diagnostics with Kali Linux within an isolated environment (local network zone).
It summarizes the entire setup process, from securing proxy communication via a Windows 11 host to configuring network routing to safely connect the Kali Linux VM on VirtualBox to a vulnerable target server (Victim Server).

---

## 0. Prerequisite Setup for VirtualBox and Kali Linux Machines

Import Kali Linux into VirtualBox and configure the network. The following includes operations gracefully executed on the Windows host side (PowerShell) and inside Kali Linux (Terminal).

1. **Import Kali Linux**
   Load the downloaded Kali Linux image (`kali-linux-2025.4-virtualbox-amd64`) into VirtualBox. You can add/import it via the GUI or use the following command example:
   ```powershell
   VBoxManage import "C:\Users\seched\Downloads\kali-linux-2025.4-virtualbox-amd64.ova"
   ```

2. **Create Internal Network (intnet7.0) and DHCP Server**
   Create an internal network (`intnet7.0`) that assigns addresses via DHCP from `10.7.0.128` to `10.7.0.191`.
   ```powershell
   .\VBoxManage dhcpserver add --netname intnet7.0 --ip 10.7.0.2 --netmask 255.255.255.0 --lowerip 10.7.0.128 --upperip 10.7.0.191 --enable
   ```

3. **Configure Kali Linux Adapters (via GUI)**
   Assign adapters from the VirtualBox GUI.
   1. Select the target VM (e.g., `kali-linux-2025.4-virtualbox-amd64`) on the VirtualBox main screen and open "Settings" > "Network".
   2. Open the **"Adapter 1"** tab and check "Enable Network Adapter".
      - **Attached to:** `Internal Network`
      - **Name:** `intnet7.0`
   3. Open the **"Adapter 2"** tab and check "Enable Network Adapter".
      - **Attached to:** `Host-only Adapter`
      - **Name:** `VirtualBox Host-Only Ethernet Adapter` (*Match the exact name used in your environment*)
   4. Click "OK" to save.

4. **Set IP Address for Host-Only Adapter on VirtualBox (192.168.56.1)**
   If a segment different from `192.168.56.x` (e.g., `192.168.57.x`) is assigned by default, change the VirtualBox settings to fix the IP.
   1. Open the VirtualBox main screen.
   2. Open "File" > "Tools" > "Network Manager" (Host Network Manager) from the menu bar.
   3. Select the target Host-Only adapter (e.g., `VirtualBox Host-Only Ethernet Adapter`).
   4. In the "Adapter" tab at the bottom, change the following and click "Apply".
      - IPv4 Address: `192.168.56.1`
      - IPv4 Network Mask: `255.255.255.0`

5. **Configure Static IP Addresses inside Kali Linux**
   After booting the virtual machine, statically set the IP addresses for each interface inside Kali Linux using NetworkManager (`nmcli`).

   The interface names (recognized by OS) and their corresponding VirtualBox adapter assignments are as follows:
   - **1st Interface** (Adapter 1 / Internal Network) : `10.7.0.3` (e.g., `eth0`)
   - **2nd Interface** (Adapter 2 / Host-Only Adapter) : `192.168.56.7` (e.g., `eth1`)

   ```bash
   # Execute in the Kali Linux terminal
   
   First, check the current interface names and NetworkManager connection names with the following commands.
   ```bash
   # Check interface names (eth0, eth1, etc.) and assigned IP addresses
   ip addr show

   # Check connection names corresponding to interface names (e.g. Wired connection 1)
   nmcli connection show
   ```

   # Apply IP settings to the 1st Interface
   sudo nmcli connection modify "Wired connection 1" ifname eth0 ipv4.method manual ipv4.addresses 10.7.0.3/24
   sudo nmcli connection up "Wired connection 1"
   
   # Apply IP settings to the 2nd Interface (Create a new connection profile)
   # Set the IP to a communicable segment (192.168.56.7) matching the 192.168.56.1/24 set in VirtualBox in Step 4.
   sudo nmcli connection add type ethernet ifname eth1 con-name "eth1-static" ipv4.method manual ipv4.addresses 192.168.56.7/24
   sudo nmcli connection up "eth1-static"
   ```

6. **Enable Auto-Start for SSH, Start Service, and Check Status**
   Start the SSH server within Kali Linux and set it to launch automatically when the OS boots. This ensures SSH is enabled automatically upon future VM startups.
   ```bash
   # Enable auto-start
   sudo systemctl enable ssh
   # Start the service
   sudo systemctl start ssh
   # Check status
   sudo systemctl status ssh
   ```

7. **Configure Kali Linux Timezone (Asia/Tokyo)**
   To align log timestamps with Japan Standard Time (JST), change the timezone to `Asia/Tokyo`.
   ```bash
   sudo timedatectl set-timezone Asia/Tokyo
   ```

## 1. Installation of WSL (Windows Subsystem for Linux) and Ubuntu
Prepare a lightweight Linux environment to run the proxy on Windows.

1. **Enable and Install WSL**
   Open Administrator PowerShell, execute the following command, and restart the PC.
   ```powershell
   wsl --install
   ```

2. **Install Ubuntu Distribution and Initial Setup**
   After rebooting, execute the following command in PowerShell to download and install Ubuntu.
   ```powershell
   wsl --install -d Ubuntu
   ```
   Immediately after installation, a new UNIX user creation screen will appear; set a username and password (e.g., `kali`).

---

## 2. Setup Proxy Server (TinyProxy) on WSL
Construct a lightweight proxy server inside Ubuntu to relay communications from Kali Linux.

1. **Install TinyProxy**
   Enter Ubuntu on WSL, update packages, and perform the installation.
   ```bash
   sudo apt-get update
   sudo apt-get install -y tinyproxy
   ```

2. **Configure Access Permissions for TinyProxy (`/etc/tinyproxy/tinyproxy.conf`)**
   Modify the configuration file to allow communication from the VirtualBox Host-Only network (`192.168.56.0/24`) and WSL's own network (`172.16.0.0/12`). Specifically, comment out `Allow 127.0.0.1` and add `Allow 192.168.56.0/24` and `Allow 172.16.0.0/12`.
   ```bash
   sudo sed -i 's/^Allow 127.0.0.1/#Allow 127.0.0.1\nAllow 192.168.56.0\/24\nAllow 172.16.0.0\/12/' /etc/tinyproxy/tinyproxy.conf
   ```

3. **Start TinyProxy Service**
   Restart the service to apply the configuration changes.
   ```bash
   sudo service tinyproxy restart
   ```

---

## 3. Windows 11 Port Forwarding Setup
Link (port proxy) proxy traffic sent from the VirtualBox network (Kali) to be forwarded to TinyProxy inside WSL.

1. **Verify WSL Network IP Address**
   Since the WSL IP fluctuates, retrieve the current IP address (e.g., `172.26.201.248`).
   ```bash
   # Command to check inside Ubuntu
   ip addr show eth0
   ```

2. **Add Proxy Forwarding Rules in Administrator PowerShell**
   (*Must be executed in Administrator PowerShell*)
   Register a rule to forward communications intended for port `8888` on the Host-Only adapter IP (`192.168.56.1`) to port `8888` of the WSL IP.
   Furthermore, to bypass a bug where the Antigravity backend (Go module) attempts direct HTTPS (port `443`) communication, add a rule to **directly forward port `443` traffic to Google's API servers (`daily-cloudcode-pa.googleapis.com`) without routing via proxy**.
   ```powershell
   # Forwarding port 8888
   netsh interface portproxy add v4tov4 listenport=8888 listenaddress=192.168.56.1 connectport=8888 connectaddress=172.26.201.248
   
   # Forward port 443 traffic directly to Google API server
   netsh interface portproxy add v4tov4 listenport=443 listenaddress=192.168.56.1 connectport=443 connectaddress="daily-cloudcode-pa.googleapis.com"
   ```

---

## 4. Windows Firewall and Routing Configuration
Grant necessary security permissions so that port-forwarded network traffic is not blocked within Windows.

1. **Allow Inbound Traffic in Windows Defender Firewall (Ports 8888, 443)**
   In Administrator PowerShell, open the ports for proxy and HTTPS.
   ```powershell
   # Port 8888
   netsh advfirewall firewall add rule name="WSL Proxy Port 8888" dir=in action=allow protocol=TCP localport=8888
   # Port 443
   netsh advfirewall firewall add rule name="WSL Proxy Port 443" dir=in action=allow protocol=TCP localport=443
   ```

2. **Enable IP Forwarding for VirtualBox Host-Only Adapter**
   Allow "relaying" (routing) from the Host-Only network to another network (WSL).
   ```powershell
   # Administrator PowerShell
   Get-NetAdapter | Where-Object { $_.InterfaceDescription -like '*VirtualBox Host-Only*' } | Get-NetIPInterface | Set-NetIPInterface -Forwarding Enabled
   ```

---

## 5. Maintain WSL (Ubuntu) Session (Prevent Suspend)

Ubuntu in WSL may suspend (stop) after a certain period if there are no active background processes, disconnecting TinyProxy communications.
To prevent this, it is recommended to keep an Ubuntu terminal open and continuously monitor the TinyProxy access logs (maintaining the session) using the following command.

```bash
# Execute in an Ubuntu terminal and leave the window open
sudo tail -f /var/log/tinyproxy/tinyproxy.log
```

---

## 6. Pre-Check for Running Antigravity Remote Window

Test the SSH connection to Kali Linux from the Windows command prompt (cmd) before opening the "Remote Window" in VS Code to run Antigravity.

1. **Add SSH Configuration for VS Code (Antigravity)**
   Add a configuration step in the SSH settings file (`C:\Users\yoned\.ssh\config`) so you can connect using an easy-to-understand hostname (`KaliLinux`) during remote connection from VS Code.
   - Open `C:\Users\yoned\.ssh\config`. (Create it if it doesn't exist).
   - Append the following content to the end of the file and save.
     ```text
     Host KaliLinux
         HostName 192.168.56.7
         User kali
     ```

2. **Connection Test from the Command Prompt**
   Launch the command prompt and attempt to connect using the following command (substituting the IP with the hostname set above).
   ```cmd
   ssh -v KaliLinux
   ```

   > [!NOTE] 
   > **[Troubleshooting 1]**
   > During verification, if you encounter the warning `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!`, please refer to "[8. Troubleshooting: 2. SSH connection Key Conflict Error](#2-ssh-connection-key-conflict-error)" at the end of this document, and retry the command after applying the fix.

3. **Verify Login**
   Upon initial login, when prompted with `Are you sure you want to continue connecting (yes/no/[fingerprint])?`, type `yes`. Input the password (default is `kali`) and verify that login succeeds. Once confirmed, logout with `exit`.

4. **Initial Remote Connection and Bulk Module Download (via NAT)**
   During the first remote connection from VS Code (Antigravity) to Kali Linux, it attempts to download server programs and extensions from the internet. Because the proxy-only route might result in communication errors or timeouts, temporarily use NAT to download the modules before starting full-scale operations.
   - **Shut down** Kali Linux entirely from the VirtualBox Manager.
   - Open Kali Linux's "Settings", assign **"NAT" to "Adapter 3"** under Network, and enable it.
   - Start Kali Linux. (This temporarily puts Kali in a state capable of direct internet access).
   - In VS Code via the Command Palette (`Ctrl+Shift+P`), select "Connect to SSH host..." and choose `KaliLinux` from the dropdown.
   - The remote window will open. After entering the SSH password, use "Open Folder", select `/home/kali`, enter the password again, and confirm that the chat responds.
   - Once verified, shut down Kali Linux again, **uncheck to disable "Adapter 3 (NAT)"**, and return to original isolation.

---

## 7. HTTP Proxy Setup in Kali Linux

### 1. Add Entries to `/etc/hosts` (Workaround for Antigravity Backend)
While this should theoretically only require Antigravity's HTTP Proxy settings, there is a bug where the Antigravity backend (Go module) ignores HTTP Proxy-related environment variables. Therefore, add the following to `/etc/hosts`:

```text
# To bypass a bug where the Antigravity backend (Go module) on Kali/Ubuntu
# ignores HTTP proxy env vars and attempts direct communication,
# strictly force DNS resolution to the Host OS IP running the proxy server (192.168.56.1),
# allowing the traffic to be routed.
192.168.56.1  daily-cloudcode-pa.googleapis.com
192.168.56.1  cloudcode-pa.googleapis.com
192.168.56.1  play.googleapis.com
192.168.56.1  www.googleapis.com
```

The hosts referenced above are destinations that the Antigravity backend attempts to access directly, bypassing proxy environment variable specifications. The reasons for setting each domain are as follows:

- **`daily-cloudcode-pa.googleapis.com` / `cloudcode-pa.googleapis.com`**:
  If omitted, you cannot reach the core Antigravity API, meaning **chat functions will fail completely (Mandatory)**.
- **`play.googleapis.com` / `www.googleapis.com`**:
  Basic chat features operate without these, but background diagnostics/telemetry sent periodically will block out, resulting in **massive spam of "Connection refused" errors** flooding the VS Code Output (Antigravity) tab. Configured cooperatively to prevent spam errors.

By forcing them to resolve to `192.168.56.1` in `/etc/hosts`, it leverages the Host OS (Windows) **Port Forwarding feature (via `netsh interface portproxy`)**, bypassing TinyProxy directly to external Google API servers as a temporary exception until the bug is resolved.

### 2. Configure HTTP Proxy in Antigravity Remote Settings
In VS Code, click the "Open a Remote Window" icon (bottom-left `><` mark), select "Connect to a SSH Host...", and choose `KaliLinux`.
When the remote window loads, configure Antigravity to communicate via proxy under the VS Code Remote (`KaliLinux`) context.
Open VS Code Settings via `File -> Preferences -> Settings`, search for "proxy" in the top bar, and modify the following items under the "Remote [SSH:KaliLinux]" tab:

- **HTTP Proxy** -> `http://192.168.56.1:8888`
- **Strict SSL Proxy** -> `OFF`
- **Server Certificates** -> `OFF`

> **※ Note**
> For detailed reasons concerning setting "Strict SSL Proxy" and "Server Certificates" to `OFF`, refer to "[9. Supplements: 2. Why Disable Strict SSL Proxy/Server Certificates in Antigravity](#2-why-disable-strict-ssl-proxyserver-certificates-in-antigravity)" at the end.

### 3. Commit Settings and Reboot to Fully Isolated Environment
Changes made in VS Code remote settings may occasionally not reflect immediately across background processes.
To reliably enforce the new proxy settings within the Antigravity module and transition into a purely "Isolated Environment (NAT disabled, Proxy-only)", follow these steps:

1. After completing proxy entries, close all active VS Code "Remote Windows".
2. Power off or execute `sudo shutdown -h now` on Kali Linux to **shut down** the system.
3. Open Kali Linux's "Settings" on VirtualBox Manager, **disable "Adapter 3 (NAT)" (uncheck)**, and return to live isolation settings.
4. Boot up Kali Linux again.
5. Reconnect to `KaliLinux` using VS Code's "Connect to SSH host...". The new proxy settings are now fully applied. Operating chat interfaces and extensions securely functions beneath isolation.

### 4. Create Antigravity Workspace Folder on Kali Linux

1. On Kali Linux, create a workspace folder with a name of your choice, e.g., `/home/kali/localwork/vulnerability_test`.
2. Select the designated folder via Open Folder in Antigravity's remote window.
3. Upon finishing work, hit "Save Workspace As..." and generate a `.workspace` file in your operational folder (consolidates chat memory and context configurations).

### 5. Operation Check (Diagnostic Instructions for Metasploitable2)

Verify whether the deployed environment (Proxy-mediated AI internet access alongside VirtualBox isolated local net usage) coordinates properly. We'll connect a vulnerable target server (Metasploitable2) on our internal network and use Antigravity (AI chat) operating over VS Code/Kali Linux to perform automatic scanning procedures.

#### 1. Setup Network and Boot Metasploitable2
1. Open VirtualBox Manager, target the imported `metasploitable2` VM, and hit "Settings".
2. Open "Network" > "Adapter 1", structure it as follows, and save.
   - **Attached to:** `Internal Network`
   - **Name:** `intnet7.0`
3. Launch the `metasploitable2` machine.
4. Upon encountering the login prompt, connect using the username `msfadmin` and password `msfadmin`.
5. Run `ip a` or `ifconfig` in the console to inspect the allotted IPv4 address.
   (*Verify an IP reflecting the DHCP range was assigned, e.g., `10.7.0.128`.*)

#### 2. Perform AI Diagnosis via VS Code (Kali Linux side)
1. Establish an SSH **Remote Connection** to `KaliLinux` using VS Code with previously resolved proxy configs. Trigger the Antigravity (Chat Window).
2. Through the chat textbox, declare the queried Metasploitable2 IP address and formulate a prompt requesting diagnostic measures.

   **[Example Instruction Prompt]**
   > `Run a port scan against the internal network asset located at 10.7.0.xxx (*discovered IP address*) via nmap. Evaluate live services and generate a vulnerability assessment concerning any potential weaknesses uncovered.`

3. The AI (Antigravity) autonomously drives tools such as `nmap` within Kali Linux. Examine its analytical responses via the reporting layout within chat.

Receiving cohesive diagnostic breakdowns effectively confirms that all infrastructure configurations properly align. This guarantees successful coordination across **AI-mediated Proxy requests (Internet-Bound)** alongside **Scanning communication across Internal Network Segments (Local boundaries)**.

---

## 8. Troubleshooting

### 1. Chat Response in Remote Window hangs indefinitely on "Generating..."

You might see "Connection refused" messages listed inside Antigravity's Output (or logged within the backend Go module). At this point, communication routing with standard AI mechanisms freezes.

**[Cause and Resolution]**
Variable dynamic IP address changes involving external Google API servers like `daily-cloudcode-pa.googleapis.com` generate routing discrepancies traversing to Windows-assigned OS Port Proxy targets (`netsh interface portproxy`).
To remediate this, you must run an administrative PowerShell sequence restarting the `iphlpsvc` routing service which forcefully refreshes established port forwarding rules.

```powershell
# Force-Refresh the System Port Proxy forwarding cache
Restart-Service iphlpsvc
```

**Reference: Related error output**
```text
026-03-24 10:20:26.617 [info] W0324 10:20:26.616773 13910 log_context.go:118] Failed to refresh cache in background: failed to get load code assist response: Post "https://daily-cloudcode-pa.googleapis.com/v1internal:loadCodeAssist": dial tcp 192.168.56.1:443: connect: connection refused
```

### 2. SSH connection Key Conflict Error

This failure frequently originates as a troubleshooting scenario amidst **"6. Pre-Check for Running Antigravity Remote Window"** procedure 2: **"Connection Test from the Command Prompt"**.

**[Cause and Resolution]**
It triggers because you've previously established SSH tunnels against identical IP addresses (or Hostnames), prompting conflicting cryptographic key mismatch issues post Virtual machine re-imports/migrations.
The terminal typically spams a similar warning layout:

```text
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
```

Locate messages such as `Offending ECDSA key in C:\Users\seched/known_hosts:26` populated in terminal logs. Use the specified row number (e.g., row 26) to perform connection history resetting protocols:

1. Launch NotePad or VS Code targeting the file `C:\Users\seched\.ssh\known_hosts`.
2. Fully delete the offending sequence targeting entities referencing `192.168.56.7` or `KaliLinux`. Save modifications.
3. Validate connection restorations executing `ssh -v KaliLinux` again via command prompt.

### 3. Procedure to Recover Settings After Temporarily Disabling or Reverting Windows Firewall

Should you disable Windows Firewall for troubleshooting applications and later click "Restore Default Values", you risk entirely clearing the manual application rules embedded within "4. Windows Firewall and Routing Configuration". Consequently, subsequent connection routing traversing Custom Proxy (Port 8888) or Google SSL Traffic (Port 443) incurs hard blocks resulting in critical remote window failures. (General Port Proxy operations alongside IP forwarding typically endure unharmed).

The following guide details identifying erased assets and restoring functional settings.

#### 1. Confirming Disappearance of Firewall Security Rule Settings

Launch Administrator PowerShell and assert commands to evaluate whether added dependencies trace existence.

```powershell
# Authenticate tracking for Custom Proxy Port 8888
netsh advfirewall firewall show rule name="WSL Proxy Port 8888"

# Authenticate tracking for Proxy Port 443
netsh advfirewall firewall show rule name="WSL Proxy Port 443"
```

**Results:**
Encountering messages reporting "No rules match the specified criteria" confirms missing settings demanding restoration protocols. (A verbose rule printout verifies robust operation).

#### 2. Execution Sequences to Re-Establish Firewall Integrations

Rules found missing demand manual execution.
Utilize an **Administrator PowerShell** session processing subsequent configurations repairing inbound allowances.

```powershell
# Re-Add inbound rule allocation for port 8888
netsh advfirewall firewall add rule name="WSL Proxy Port 8888" dir=in action=allow protocol=TCP localport=8888

# Re-Add inbound rule allocation for port 443
netsh advfirewall firewall add rule name="WSL Proxy Port 443" dir=in action=allow protocol=TCP localport=443
```

### 4. VS Code Server Download Errors Occurring During Kali Linux Remote SSH Connections

Updated instances occurring towards Windows-Hosted VS Code client dependencies demand appropriately matched iterations of "VS Code Server" fetched and aligned internally to the VM (Kali Linux).
Unfortunately, Initial download phase mechanisms inherent to VS Code systematically lack automatic proxy implementation compatibility resulting in terminal logging traces reading `Error downloading server from all URLs` or `installation failed`, generating hard stops mitigating further connections.

Counteract failing instances executing temporary protocols involving booting via authorized internal NAT connections allowing targeted file extraction without firewall/proxy manipulation errors:

1. **Perform System Shutdown for Kali Linux**
   Shutdown currently active instances targeting Kali Linux utilizing VirtualBox UI manipulation or Terminal (`sudo shutdown -h now`).
2. **Temporarily Authorize Internal NAT Integrations**
   Within VirtualBox managing settings targeting Kali Linux VMs, open "Network" configurations and dynamically construct **"Adapter 3" selecting implementations tagged "NAT" and verify enablement** (generate blank setups if unassigned previously).
3. **Execute Boot Iterations and Recouple Remote Connecting Paths**
   Boot up Kali Linux dynamically post adapter allocations. Direct VS Code to deploy remote windows targeting established connections via `KaliLinux`. Input correct passwords allowing background executions allocating functional instances governing proper fetches mapping VS Code Server extensions transparently relying on active NAT provisions.
4. **Appraise Connectivity and Workspace Responses**
   Verify lower-left user overlays printing successfully initialized properties tracing `SSH:KaliLinux`. Ensure explorer arrays unearth internal tree arrays asserting successful operations spanning isolated systems.
5. **Neutralize Associated NAT Protocols (Return to Default Environmental Isolation)**
   Post resolution sequences, shut down operations traversing standard structures to **uncheck enablement associated with "Adapter 3 (NAT)"** protocols returning environment conditions masking behind configured closed-loop Local Proxy iterations securely.

---

## 9. Supplements

### 1. Procedures Outlining Re-Configurations Amidst Internal Network Segment Alterations for Kali Linux

Assuming dynamic internal network naming swaps translating from `intnet13` converting structures integrating `intnet7.0` paired against Kali Linux IP modifications cascading from `192.168.13.140` pointing allocations resolving towards `10.7.0.3`. Proceed with updates utilizing mapped configurations:

#### [Pre-Execution Preparations (Targeting Windows Host Systems)]

1. **Deploy Formatted DHCP Instances**
   Initiate standard PowerShell windows leveraging the following to deploy and activate functional Internal Server nodes spanning specified subnets:
   ```powershell
   .\VBoxManage dhcpserver add --netname intnet7.0 --ip 10.7.0.2 --netmask 255.255.255.0 --lowerip 10.7.0.128 --upperip 10.7.0.191 --enable
   ```
2. **Map System-Level VirtualBox Target Adjustments**
   From standard VirtualBox Main environments, target Kali Linux VM objects > select "Settings" > navigate "Network" allocations interacting with "Adapter 1". Redefine labeled values mirroring internal array updates targeting naming instances matching (`intnet7.0`) and apply via "OK".

#### [Execution Steps Required Post Machine Bootings (Within Kali Linux Contexts)]

1. **Static Configurations Modifying Integrated OS Assignments**
   Acquire terminal instances natively inside running instances mapping structural 1st interface routing points bridging configured new segment architectures updating values gracefully.
   ```bash
   # Reassign structured 1st Interface internal IP segments
   sudo nmcli connection modify "Wired connection 1" ipv4.addresses 10.7.0.3/24
   # Systematically restart connection services implementing operational data
   sudo nmcli connection up "Wired connection 1"
   ```
   *If manual implementation leverages paths incorporating configurations linked to `/etc/network/interfaces`, swap data tracking matched references specifying paths mapped containing `address` variables switching entries towards target properties evaluating `10.7.0.3`. Finalize modifications applying generalized reboot iterations or routing network services (`sudo systemctl restart networking`).*

*(Supplement)*
When adapting only properties nested spanning structural "Internal Network (Adapter 1)", secondary host operations leveraging instances associated with "Host-Only Ethernet assignments (Adapter 2 containing `192.168.56.x` properties)" generate zero impact preventing necessity modifications required targeting Windows-sided port forwarding loops paired alongside specific integrated standard HTTP Proxy specifications assigned covering VS Code operations allowing persistent stable behavior undisturbed.

### 2. Why Disable Strict SSL Proxy/Server Certificates in Antigravity

Attempting external HTTPS communications via Proxy structures (particularly mapped leveraging integrated WSL TinyProxy objects) triggers generalized verification issues. Specifically, instances associated with standard validation phases (TLS Handshaking logic) evaluating internal Proxy Certification tracking combined with target node resolutions spanning domains governing Remote API connections (i.e. Google infrastructure systems), resulting in robust errors cascading communication blocks spanning associated integrated nodes yielding halted "Generating..." system responses generating failures blocking progress.

By design, our layout encompasses structured validation operating amidst intrinsically verifiable closed-loop proxy domains generating requirements forcing targeted configurations. Applying states forcing manipulations where **"Strict SSL Proxy" sits assigned evaluating properties disabled enforcing nullification bypassing native internal routing verification** while simultaneously enforcing mapped properties disabling **"Server Certificates" implementing conditions allowing integrated bypassing operations preventing target connection structural certification errors** securely allows two-tier robust communication arrays blocking intrinsic failures securely preventing functional disruption scenarios completely.
