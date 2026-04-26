# Setup of a Robot Simulation Environment Using EtherNet/IP Communication (Docker Application)

This document summarizes the steps to execute the "EtherNet/IP MES-PLC-Robot Integration Simulation" built using open-source tools. We have introduced Docker and Docker Compose to automate network configuration as well as the starting and stopping of processes.

## 1. Operating Environment and Architecture Overview

| Item | Details |
| --- | --- |
| **OS Environment** | Ubuntu 24.04 Desktop (on VirtualBox Virtual Machine) |
| **Development Language** | Python 3.12 |
| **PLC (Server)** | Docker containerized (`enip_sim_plc`) / 10.7.1.37<br>Software EtherNet/IP virtual amplifier/server (`cpppo`) |
| **MES (Client)** | Docker containerized (`enip_sim_mes`) / 10.7.1.38<br>Client issuing commands via the EtherNet/IP protocol |
| **Robot Rendering** | Executed on the Host OS (`pybullet`)<br>Real/Virtual physical simulation with inverse kinematics calculation and rendering |

**Architecture Overview:**
A Docker `macvlan` network (10.7.1.x) is constructed within the Host OS. A Virtual PLC (Server) and an "MES client issuing commands" are launched as independent containers. A "Robot client that operates in the physical world by monitoring states" connects to this network from the Host OS. The three components integrate by communicating via the PLC's memory (tags).

---

## 2. [First Time Only] Initial Setup on a New Server (When Building from Scratch)

When setting up the environment from scratch on a new Ubuntu 24.04 server, perform the following preliminary preparations before running the simulation. (If the environment is already built, proceed to "3. Simulation Execution Procedure.")

### Preparation 1. Install Necessary Packages and Docker
Starting from a clean Ubuntu state, install Python's virtual environment creation tool and Docker-related packages.
```bash
sudo apt update
sudo apt install -y python3-venv docker.io docker-compose
```

### Preparation 2. Check and Modify Network Interface Name (Important)
Depending on your environment, the parent network interface name for macvlan (e.g., `enp0s3`, `eth0`, `ens33`, etc.) may vary.
1. Run the `ip a` command to find the interface name that holds the IP currently used for standard communication.
2. If it is NOT `enp0s3`, open the following two files in advance and replace the interface name with your actual one:
   - `setup_network.sh`: `PARENT_INTERFACE="enp0s3"`
   - `docker-compose.yml`: `parent: enp0s3`

### Preparation 3. Setup Host Robot Simulator (venv) Environment
To render the robot on the Host OS side, prepare a Python virtual environment and the required packages.
```bash
cd /home/kali/localwork/enip_sim
python3 -m venv venv
source venv/bin/activate
pip install pybullet cpppo
```
Once this preparation is complete, you can seamlessly proceed to "3. Simulation Execution Procedure" hereafter.

---

## 3. Simulation Execution Procedure (Daily Start and Stop)
Since the robot simulator runs on the Host OS, open a terminal on FADockerHost and take the following steps.

### Step 1. Prepare Host-Side Network
Create a routing bridge to enable mutual communication from the host OS to the macvlan network where the containers belong.
*Note: This only needs to be run once after booting the OS, before running the simulation.*
```bash
cd /home/kali/localwork/enip_sim
./setup_network.sh
```

### Step 2. Build and Start Containers (PLC Server / MES Client)
Use Docker Compose to automatically build images and start the PLC server and MES client containers in the background. Including the correct boot sequence, they will launch with a single command.
```bash
sudo docker-compose up -d --build
```
If there have been absolutely no changes to the files that make up the Docker images, `--build` is unnecessary.
```bash
sudo docker-compose up -d
```

*Note: You can check the boot status with `sudo docker-compose ps`. The MES container will only launch after the PLC container has successfully started.*

### Step 3. Execute the Robot Simulator
Start the robot simulator on the host, specifying the target PLC's IP (`10.7.1.37`) to monitor.
```bash
cd /home/kali/localwork/enip_sim
source venv/bin/activate
PLC_IP=10.7.1.37 python robot_sim.py
```
After starting up, it will detect the "Pick" command sent by the MES, and physical processing will commence.
If you need to execute `PLC_IP=10.7.1.37 python robot_sim.py` again, note that the mes container might have stopped, so run:
```bash
sudo docker-compose start mes
```
before you run `PLC_IP=10.7.1.37 python robot_sim.py`.

### Step 4. End the Simulation
When finished, cleanly stop and remove the group of Docker containers running in the background.
```bash
sudo docker-compose down
```

---

## 4. Communication Packet Capture Configuration for Monitor Server (IDS, etc.)

In plant cybersecurity exercises, it is generally common to set up a monitor server (e.g., an Intrusion Detection System, like `10.7.1.32`) to observe and analyze network traffic.

However, since this configuration utilizes a "Docker Macvlan Network," communication between containers (`enip_sim_plc` and `enip_sim_mes`) running on the same host does not physically leave the network interface (e.g., `enp0s3`). Instead, it securely loops back directly within the Linux kernel's virtual Macvlan switch.

Because of this, **a phenomenon occurs where zero packets flow to an external device or a monitor server on a separate virtual machine.** Therefore, merely setting the monitor server's interface to promiscuous mode will not let you capture EtherNet/IP packets.

To solve this and **perfectly replicate in software the "mirror port (SPAN port) of an L2 switch"** used in production plant environments, we utilize standard Linux kernel functionality (packet duplication via the `iptables TEE` target).

### Configuration Procedure (Packet duplication using iptables TEE)

Here, we will step into the network namespace of the `enip_sim_plc` container—the "target" of the communications—and add rules to duplicate and send an exact copy of the EtherNet/IP communication packets (TCP Port 44818) to the monitor server (`10.7.1.32`). This allows all packets, whether commands from the MES or packets from the robot simulator on the host, to be correctly captured.

**1. Add a port mirroring rule on the Docker host machine**
Run the following commands on the Docker host machine (Kali Linux) to apply rules to the PLC container's inbound and outbound paths.

```bash
# Forward a copy of the requests received by the PLC (Destination port 44818) to the monitor server
sudo nsenter -t $(sudo docker inspect -f '{{.State.Pid}}' enip_sim_plc) -n \
  iptables -t mangle -A PREROUTING -p tcp --dport 44818 -j TEE --gateway 10.7.1.32

# Forward a copy of the responses sent by the PLC (Source port 44818) to the monitor server
sudo nsenter -t $(sudo docker inspect -f '{{.State.Pid}}' enip_sim_plc) -n \
  iptables -t mangle -A POSTROUTING -p tcp --sport 44818 -j TEE --gateway 10.7.1.32
```

**2. Confirm Capture on the Monitor Server side**
On the monitor server's (`10.7.1.32`) terminal, confirm that communications can be acquired by running a tool like `tcpdump`.
*Note: Even though the destination IP is not meant for itself, the packets are sent aiming at the target's MAC address, so they are visible on the capture tool.*

```bash
# Execute capture on the monitor server side interface (e.g., enp0s3)
sudo tcpdump -i enp0s3 -n port 44818
```

This setup makes it fully possible to observe raw traffic with packet dump tools or an Intrusion Detection System (Snort, Suricata, etc.) exactly as if monitoring through a physical mirror port.

> [!IMPORTANT]
> **About Configuration Volatility**
> This mirroring function accomplished by `iptables` resides in memory. Consequently, **the settings are completely erased every time the OS (host machine) restarts or the containers restart/recreate (via `docker-compose down` / `up`, etc.).**
> If you wish to capture traffic again, you must definitely execute these exact same steps (running the commands above) every time after the containers boot.

---

## Addendum

### 1. Internal Specifications for Container and Network Management by Docker Compose

`docker-compose.yml` oversees both the creation of the system's core "virtual network environment" and the integrated management of the "individual node (container) processes."

*   **Network Definition (`macvlan`)**:
    *   Creates a `macvlan` network (`pub_net`) having a subnet of `10.7.1.0/24`, setting the Host OS (`enp0s3`, etc.) as the parent interface.
    *   This allows each container to communicate directly as if assigned its own IP address (`10.7.1.x`) like a discrete piece of equipment on a physical network.
*   **PLC Container (`enip_sim_plc`)**:
    *   Automatically builds a background execution image incorporating Python and the `cpppo` library using `Dockerfile.plc`.
    *   Upon startup, it is assigned a static IP of `10.7.1.37` and maintains a waiting state, actively listening to requests on EtherNet/IP's TCP/44818 port on the network.
*   **MES Container (`enip_sim_mes`)**:
    *   Automatically builds the `mes_client.py` execution environment image using `Dockerfile.mes`.
    *   Assigned a static IP of `10.7.1.38`. Moreover, through the `depends_on` configuration, sequence control is established to ensure this container only launches after the PLC container has booted.
    *   By injecting the environment variable `PLC_IP=10.7.1.37` internally, the connection target for the script is dynamically directed towards the PLC host.

---

### 2. Operational Comparison of `docker-compose` and Pure `docker` Commands

In scenarios where multiple containers are coupled into one system, such as our "PLC Server" and "MES Client" simulation setup, managing it via `docker-compose` proves overwhelmingly superior to individually firing pure `docker` commands. Below is a comparison of the effort involved in building, starting, and stopping.

#### [Comparison Table] Build, Start, Stop Commands

| Operational Phase | Manual Operation using Pure `docker` Commands (Run per container) | Batch Operation using `docker-compose` (Current Method) |
| :--- | :--- | :--- |
| **Preparation (Network Settings)** | `docker network create -d macvlan --subnet=10.7.1.0/24 -o parent=enp0s3 pub_net` | **Unnecessary** (Pre-defined in `docker-compose.yml`) |
| **Build (Create Images)** | `docker build -t enip_sim_plc -f Dockerfile.plc .`<br>`docker build -t enip_sim_mes -f Dockerfile.mes .` | **Unnecessary** (Handled in yml)<br>Autobuild with the single strike of `docker-compose up -d --build` |
| **Start (Execute)** | `docker run -d --name enip_sim_plc --network pub_net --ip 10.7.1.37 enip_sim_plc`<br>`docker run -d --name enip_sim_mes --network pub_net --ip 10.7.1.38 -e PLC_IP=10.7.1.37 enip_sim_mes` | **Single Command**<br>`docker-compose up -d` |
| **Stop (Halt & Cleanup)** | `docker stop enip_sim_mes enip_sim_plc`<br>`docker rm enip_sim_mes enip_sim_plc` | **Single Command**<br>`docker-compose down` |

#### Why `docker-compose` is Better Suited for System Construction

1. **Automatic Initialization Sequencing**
   The MES client will result in an error if the connection target (PLC server) hasn't booted up yet. With pure Docker commands, a human has to boot them manually in order or a complex shell script must be crafted (like the old `start.sh`). With Compose, simply writing `depends_on: - plc` natively guarantees the order of PLC → MES.
2. **Prevent Network and Environmental Variable Misconfigurations**
   Multiple containers must belong to the exact same network (`pub_net`) and perfectly share correct environment variables (like `PLC_IP=10.7.1.37`). Because everything is encoded as a `.yml` file (Infrastructure as Code), the risk of typing mistakes or missing configurations via manual inputs disappears.
3. **Integrated Lifecycle Management**
   The continuous action of "batch building, booting, and subsequently tearing everything down cleanly" finishes fully through just `up` and `down`. Operating on pure `docker` commands can easily leave obsolete container processes lingering post-stop, minimizing the risk of errors appearing on the next boot (e.g., port conflicts, name collisions).

---

### 3. Project File Composition

To reproduce this system on a brand new Ubuntu environment or GitHub, the complete and necessary cluster of files are:

* **[Infrastructure/Network Definition Level]**
  * `docker-compose.yml`
  * `setup_network.sh`
* **[Docker Containers (PLC / MES) Level]**
  * `Dockerfile.plc`
  * `Dockerfile.mes`
  * `mes_client.py` (Script utilized inside the MES container)
* **[Host OS (Robot) Level]**
  * `robot_sim.py` (Script directly running on the Host OS)
  * `requirements.txt` (Declares packages to install to your host OS venv: pybullet, cpppo, etc.)

### 4. Note on 3D Model Data

All the 3D model data utilized inside `robot_sim.py`—such as the robot arm (KUKA iiwa), blocks, or floor—are fundamentally utilizing the default built-in dataset intrinsically provided within the installed `pybullet` package (registered in `requirements.txt`).
Consequently, there is no need to manually push heavy 3D model files into GitHub; making this an absolutely cleanly structured, completely self-sustained working repository just by carrying over this set of codes.
