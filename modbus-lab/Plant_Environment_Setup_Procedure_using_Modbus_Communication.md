# Plant Environment Setup Procedure using Modbus Communication

This document describes the procedure for setting up a plant environment using Modbus communication on an Ubuntu 24.04 Server.

## Components
| Type | Purpose | Implementation Format |
|---|---|---|
| Modbus Server | PLC for BPCS | Docker on Ubuntu 24.04 |
| Modbus Client | OCS (SCADA) | Docker on Ubuntu 24.04 |

## Source Program Structure

In this configuration, the simulation environment is operated by building and containerizing the source programs on the host side. The outline of the processing implemented in each script is as follows.

### 1. `plc/server.c` (PLC / Modbus Server)
* **Language/Library**: C language (`libmodbus`)
* **Implementation Overview**: A Modbus TCP server intended to act as plant equipment (sensors, valves, etc.) in a gas plant. It retains various current states and parameters in its internal memory area (registers, coils, etc.), and responds with values or overwrites them in response to requests (queries) from the SCADA.
* **Extensibility**: By adding physical equations to this program, such as "liquid level changes in response to valve operation," it can be evolved into a more authentic plant simulator.

### 2. `scada/app.py` (SCADA / Modbus Client)
* **Language/Library**: Python (`Flask`, `pymodbus`)
* *(Note: `scada/templates/index.html` serves as the GUI frontend)*
* **Implementation Overview**: A communication intermediary operating as both a web server and a Modbus client.
* **Periodic Reading (Monitoring)**: It accesses the PLC emulator (10.7.2.37:502) every few seconds, retrieves various numerical values collectively (polling), and delivers them to the Web (JavaScript) as JSON.
* **Writing (Operation)**: When settings are changed via operations on the screen, it immediately goes to write those setting values to the holding registers of the PLC.

---

## 1. Preparing VirtualBox and Ubuntu 24.04 server

### 1.1 Downloading Software
1. **Download and Install VirtualBox**
   - Download the installer for Windows hosts from the [VirtualBox Official Website](https://www.virtualbox.org/) and install it.
2. **Obtain the Ubuntu 24.04 LTS Server ISO Image**
   - Download the ISO image (.iso file) of `Ubuntu 24.04.x LTS Server` from the [Ubuntu Official Download Page](https://ubuntu.com/download/server).

### 1.2 Importing Ubuntu 24.04 server
   
   1. Launch VirtualBox and click "New".
2. Set the Name (`PlantDockerHost Ubuntu24.04 server`), ISO image (select the downloaded Ubuntu ISO), check "Skip Unattended Installation (*Recommended*)", and proceed to "Next".
3. **Hardware**:
   - Base Memory (RAM): Recommended **4096 MB** (4GB) or more
   - Processors: Recommended **2 CPU** or more
4. **Hard Disk**:
   - Create a Virtual Hard Disk: Allocate **40 GB** or more, then click "Next" -> "Finish".

### 1.3 Adapter Settings for Ubuntu 24.04 server (Performed in GUI)
   Assign adapters from the VirtualBox GUI.
   1. Select the target VM (PlantDockerHost Ubuntu24.04 server) on the VirtualBox main screen and open "Settings" > "Network".
   2. Open the **"Adapter 1"** tab and check "Enable Network Adapter".
      - **Attached to:** `Internal Network`
      - **Name:** `intnet7.2`
   3. Open the **"Adapter 2"** tab and check "Enable Network Adapter".
      - **Attached to:** `NAT`
      - Port Forwarding
        Name: SSH, Protocol: TCP, Host Port: 7236, Guest Port: 22
      * Port forwarding is used for internet connection and SSH from the host OS. Enable this only during development.
   4. Click "OK" to save.

### 1.4 Assigning a DHCP Server to the Internal Network (intnet7.2)
   Assign addresses via DHCP to the internal network (`intnet7.2`) from `10.7.2.128` (up to `10.7.2.191`). Set 10.7.2.3 to 10.7.2.127 as the static IP address allocation range.

   ```powershell
   .\VBoxManage dhcpserver add --netname intnet7.2 --ip 10.7.2.2 --netmask 255.255.255.0 --lowerip 10.7.2.128 --upperip 10.7.2.191 --enable
   ```

### 1.5 Installing Ubuntu 24.04 Server
1. "Start" the virtual machine.
2. In the language selection, choose `English`. (It is strongly recommended to install and operate the Server version in English rather than Japanese).
3. Follow the on-screen instructions, configure the keyboard layout (Japanese), etc.
4. **Network Configuration**: Leave as default and select `Done`.
5. **Storage Configuration**: Leave as default and select `Done`.
6. **Profile Setup**: Set your username (e.g., `kali`), password, etc.
7. **SSH Setup**: **Make sure to check ([X]) "Install OpenSSH server" using the Space key.**
8. **Featured Server Snaps**: Since we will install the latest version of Docker from its official repository, leave all unchecked and select `Done`.
9. Once the installation is complete, select `Reboot Now`. (*If the message "Please remove the installation medium" appears, press the Enter key to reboot).

### 1.6 Configuring SSH Server for Automatic Startup
   
   Configure it to start automatically when the OS boots. This ensures SSH is automatically enabled upon subsequent VM startups.
   ```bash
   # Enable automatic startup
   sudo systemctl enable ssh
   # Start the service
   sudo systemctl start ssh
   # Check status
   sudo systemctl status ssh
   ```

### 1.7 Configuring Static IP Address in PlantDockerHost Ubuntu 24.04 server
   After starting the virtual machine, statically set the IP address for each interface using the yaml file under `/etc/netplan/`.

   Checking interface names:
   ```bash
   ip addr show
   ```

   Assume the interface names are `enp0s3` (Internal Network) and `enp0s8` (NAT) (*Adjust accordingly if different*).
   Create/edit `/etc/netplan/99-netcfg.yaml`.

   ```bash
   sudo nano /etc/netplan/99-netcfg.yaml
   ```

   **Description content:** (Since it's PlantDockerHost, the IP will be 10.7.2.36)
   ```yaml
   network:
     version: 2
     renderer: networkd
     ethernets:
       # --- Adapter 1: Internal Network (intnet7.2) ---
       enp0s3:
         dhcp4: false
         addresses:
           - 10.7.2.36/24
         # nameservers:
         #   addresses: [10.7.2.1] # Use internal DNS if available in the future
   
       # --- Adapter 2: NAT (for Host-to-Guest SSH) ---
       enp0s8:
         dhcp4: true
   ```
   After saving, apply the configuration.
   ```bash
   sudo netplan apply
   ```
   Verify that you can log in from the host OS terminal with the following:
   ```bash
   ssh -p 7236 kali@127.0.0.1
   ```

### 1.8 Timezone Setup (Asia/Tokyo) for PlantDockerHost Ubuntu 24.04 server
   To align the log timestamps with Japan Standard Time (JST), change the timezone to `Asia/Tokyo`.
   ```bash
   sudo timedatectl set-timezone Asia/Tokyo
   ```
---

## 2. Setting up the Docker Environment on the Guest OS

### 2.1 Update Packages
```bash
sudo apt update
sudo apt upgrade -y
```

### 2.2 Add Docker's Official GPG Key and Repository
Install the latest official version of Docker rather than the standard Ubuntu Docker.
```bash
# Install prerequisite packages
sudo apt install -y ca-certificates curl

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add Docker to the Apt repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package list 
sudo apt update
```

### 2.3 Install Docker and Docker Compose
```bash
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 2.4 Verify Installation
```bash
sudo docker --version
sudo docker compose version
```
If version information is displayed for each, the Docker environment setup is complete.

---

## 3. Project Structure and Creating docker-compose.yml

In this case, we use the **Macvlan network** directly assign IP addresses from the same subnet as the VirtualBox Ubuntu host to each Docker container (Modbus server, client). This makes IP communication (ping and Modbus communication) possible from the outside (like Kali Linux) to the containers.

 ### 3.1 Move to Project Directory
```bash
# (Move to the project directory)
cd /home/kali/localwork/plant
```

### 3.2 Create docker-compose.yml
Create `docker-compose.yml` in the project directory with the following content.
(*Adjust the `parent: enp0s3` part to match the Ubuntu main interface name confirmed with the `ip a` command*).

```yaml
services:
  # 1. PLC for BPCS (Modbus Server 1)
  modbus-bpcs:
    build: ./plc
    container_name: modbus-bpcs
    networks:
      scada-net:
        ipv4_address: 10.7.2.37

  # 3. OCS/SCADA (Modbus Client)
  scada-client:
    build: ./scada
    container_name: scada-client
    ports:
      - "5000:5000"
    volumes:
      - ./scada:/app
    environment:
      - PLC_IP=10.7.2.37
    depends_on:
      - modbus-bpcs
    networks:
      scada-net:
        ipv4_address: 10.7.2.39

networks:
  scada-net:
    driver: macvlan
    driver_opts:
      # Specify Ubuntu's main network interface (check with ifconfig or ip a)
      parent: enp0s3
    ipam:
      config:
        - subnet: 10.7.2.0/24
          # Escape container IP pool to spare space (240-255) to avoid conflict with other static IPs
          ip_range: 10.7.2.240/28
```

---

## 4. Container Startup and Connectivity Check

Start the containers and verify if direct communication is possible from the host OS or another machine like Kali Linux.
Execute the following commands in the project directory.

```bash
# Remove old network conflicts (if necessary)
# sudo docker network prune -f

# Build and start containers in the background
# (Move to the project directory)
cd /home/kali/localwork/plant
sudo docker compose build
sudo docker compose up -d
```
Enable promiscuous mode so that dockers attached to macvlan from other machines connected to the internal network can receive communications.
```bash
sudo ip link set dev enp0s3 promisc on
```

Once started, `ping` the IP address of each container from another virtual OS (e.g., Kali Linux) on the internal network to verify connectivity.
* BPCS (Modbus Server 1): **10.7.2.37**
* SCADA Client: **10.7.2.39**

```bash

ping -c 4 10.7.2.37
ping -c 4 10.7.2.39
```

If responses return normally, the plant environment setup using the Macvlan network is complete.

## 5. Displaying SCADA HMI on Kali Linux

The plant's SCADA server possesses an API for delivering plant current values alongside `index.html` as the GUI base.
When accessing this `index.html` via a browser on Kali Linux within the internal network, the browser-side program (JavaScript) continuously retrieves data dynamically from SCADA, allowing the screen to update in real-time.

On Kali Linux's Firefox, access
http://10.7.2.39:5000
to display the SCADA HMI. You can confirm the HMI is shown by projecting the Kali Linux screen to the host OS via RDP.

### 5.1 Connecting to Kali Linux via RDP from Windows 11 Host OS

The following are the setup steps for connecting to Kali Linux via Remote Desktop (RDP) from a Windows 11 host OS.

#### 5.1.1 Check xrdp Installation Status
On Kali Linux, check if xrdp is already installed by displaying its version.
```bash
xrdp -v
```
If version information (E.g., `xrdp 0.9.21.1`) is displayed, it is installed. If it outputs "command not found", proceed with installation via the steps below.

#### 5.1.2 Add Network Configuration (For Internet Connection)
An internet connection is required to install xrdp. Temporarily add **NAT connection** or similar in the VirtualBox settings, connect to the internet, and reboot.

#### 5.1.3 Install and Enable xrdp
Once connected to the internet, execute the following commands on Kali Linux.
```bash
sudo apt update
sudo apt install -y xrdp

# Enable and start the service
sudo systemctl enable xrdp
sudo systemctl start xrdp
```

#### 5.1.4 Check Startup Status
Check if the service is running normally.
```bash
systemctl status xrdp
```

#### 5.1.5 Create Session Information
On Kali Linux, set it up to launch the XFCE desktop upon RDP connection.
```bash
echo "xfce4-session" > ~/.xsession
```

#### 5.1.6 Addressing Firefox Input Issues
If Firefox hardware acceleration is enabled, input issues via RDP (such as the Enter key not working) may occur. In this case, perform the settings below to switch to "Software rendering".

**Configuration Steps:**
- Set `layers.acceleration.disabled` to `true`
- Set `gfx.webrender.software` to `true`

**One-liner command for bulk setting:**
```bash
find ~/.mozilla/firefox/ -name "prefs.js" -exec sh -c "echo 'user_pref(\"layers.acceleration.disabled\", true);' >> {}; echo 'user_pref(\"gfx.webrender.software\", true);' >> {}" \;
```

After configuration, log out locally on Kali Linux, and connect using the "Remote Desktop Connection" from Windows 11 by specifying Kali Linux's IP address: 192.168.56.7.
Connect, and check via Kali Linux's Firefox at
http://10.7.2.39:5000.
If the screen is displayed, the PLC/SCADA operation check is complete. Shut down Kali Linux and disable the NAT connection.

## 6. Traffic Packet Capture Configuration on Monitor Server (IDS, etc.)

In plant cybersecurity exercises, a monitor server (IDS: Intrusion Detection System, etc., e.g., `10.7.2.32`) is set up to monitor and analyze network traffic.

In this setup, we utilize "Docker Macvlan network", and communication between containers running on the same host (Kali/Ubuntu) (`10.7.2.37` and `10.7.2.39`) does not get sent out of the physical network interface (e.g., `enp0s3`). It loops back internally within the virtual Macvlan switch inside the Linux kernel.

Because of this, **no packets flow out to the VirtualBox Internal Network side**, and traffic packets do not reach the monitor server's interface.

Therefore, we use the standard Linux kernel feature (`iptables TEE` target for packet duplication) to **simulate a physical environment's "L2 Switch Mirror Port (SPAN Port)" in software**. Procedures are provided below.

### 6.1 Setup Procedure (Packet Duplication with iptables TEE)

Here, we will enter the `10.7.2.39` (SCADA container) network namespace and add a rule to duplicate/send an exact copy of Modbus communication packets (TCP port 502) to the monitor server (`10.7.2.32`).

**1. Add port mirroring rules on the Docker host side**
Run the following commands to apply rules at the entry and exit points of the `scada-client` container.

```bash
# Forward a copy of requests (destination port 502) sent from the SCADA client to the monitor server
sudo nsenter -t $(sudo docker inspect -f '{{.State.Pid}}' scada-client) -n \
  iptables -t mangle -A POSTROUTING -p tcp --dport 502 -j TEE --gateway 10.7.2.32

# Forward a copy of responses (source port 502) returning to the SCADA client to the monitor server
sudo nsenter -t $(sudo docker inspect -f '{{.State.Pid}}' scada-client) -n \
  iptables -t mangle -A PREROUTING -p tcp --sport 502 -j TEE --gateway 10.7.2.32
```

**2. Verify Capture on the Monitor Server Side**
On the monitor server's (`10.7.2.32`) terminal, execute `tcpdump` or similar tools, and verify that traffic can be captured over the interface set in promiscuous mode.

```bash
# Set the target interface (e.g., enp0s3) to promiscuous mode
sudo ip link set dev enp0s3 promisc on

# Run capture on the monitor server's interface
sudo tcpdump -i enp0s3 -n port 502
```

By applying this configuration, it becomes possible to have packet dumps or Intrusion Detection Systems (Snort, Suricata, etc.) monitor raw traffic entirely as if connected to a physical mirror port.


> [!IMPORTANT]
> **About Configuration Volatility**
> This mirroring functionality provided by `iptables` consists of in-memory settings. Therefore, **the settings are cleared every time the OS (host machine) reboots, or when the containers restart/recreate.**
> If you wish to capture communications again, you must rerun the same procedure (executing the above commands) each time following the container launch.

* To manually disable mirroring, restart the container, or substitute `-A` with `-D` in the above commands to execute deletion.

---

## 7. Supplementary Information

### 7.1 How to Run Docker Commands Without sudo

If you want to avoid entering `sudo` every time, adding the current user to the `docker` group will allow Docker commands to be run without `sudo`.

```bash
sudo usermod -aG docker $USER
```

* To reflect the settings, either log out securely using `exit` and SSH back in, or execute the `newgrp docker` command.

---

### 7.2 Regarding Macvlan Promiscuous Mode

When using Macvlan, the physical interface used by the Docker host (e.g., `enp0s3`) must be turned to **promiscuous mode**. Enable it and check it using the following commands.

```bash
# Change the interface name (e.g., enp0s3) as needed for your environment
sudo ip link set dev enp0s3 promisc on

# Confirm that PROMISC is added after state UP...
sudo ip addr show enp0s3
```

### 7.3 Why is Promiscuous Mode Necessary?

Usually, a network interface (LAN Card) is designed to accept incoming packets directed to "its own MAC address" while discarding others. However, when using the Docker Macvlan network, multiple "virtual MAC addresses distinct to each container" are created upon a single physical (or virtual) network interface.

By enabling promiscuous mode, the interface can receive incoming packets intended for "MAC addresses that aren't itself" (i.e., targeted at the containers) without dropping them, successfully passing incoming external traffic onto the containers.

---
