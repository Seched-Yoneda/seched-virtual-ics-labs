# EtherNet/IP Robot Simulation Lab (enip-lab)

This repository provides an open-source, Docker-based simulation environment that integrates a **Manufacturing Execution System (MES)**, a **Programmable Logic Controller (PLC)**, and a **3D Robot Simulator** communicating over the **EtherNet/IP** (ENIP/CIP) protocol.

## 🌟 Overview

The simulation environment demonstrates a realistic industrial automation workflow:
1. **MES (Client)**: Sends operational 'Pick' commands via EtherNet/IP.
2. **PLC (Server)**: A virtual PLC (powered by `cpppo`) receives the command and updates its internal memory tags.
3. **Robot (Simulator)**: A physical simulation (using `pybullet`) passively monitors the PLC's tags and executes a 3D pick-and-place animation in real-time.

By containerizing the MES and PLC using Docker Compose on an orchestrated `macvlan` network, this setup accurately replicates physical plant logic in software. It is highly suitable for industrial cyber-security exercises, traffic interception (e.g., via IDS/Monitor Servers), and general OT network testing.

## 📄 Documentation

Comprehensive, step-by-step instructions on setting up the environment, routing networks, and executing the simulation are provided in both English and Japanese:

* 🇬🇧 **English**: [Setup_Robot_Simulation_Environment_using_EtherNet_IP_EN](Setup_Robot_Simulation_Environment_using_EtherNet_IP_EN.md)
* 🇯🇵 **Japanese**: [EtherNet-IP通信を利用するロボットシミュレーション環境の構築](EtherNet-IP通信を利用するロボットシミュレーション環境の構築.md)

## 📁 Repository Structure

* **Infrastructure & Network**
  * `docker-compose.yml`: Automates building and launching the PLC and MES containers on a dedicated subnet.
  * `setup_network.sh`: Configures the host OS routing bridge to connect with the Docker containers.
* **Containers (Nodes)**
  * `Dockerfile.plc`: Blueprint for the virtual PLC server.
  * `Dockerfile.mes` & `mes_client.py`: Blueprint and execution script for the MES command client.
* **Host Application**
  * `robot_sim.py`: The live 3D robot physics simulation (needs to be run directly on the Host OS).
  * `requirements.txt`: Required Python packages for the virtual environment (e.g., `pybullet`, `cpppo`). Note: All 3D models are built into the pybullet package.

## 🚀 Quick Start

1. **Setup Host Network**: Create the routing bridge by running:
   ```bash
   ./setup_network.sh
   ```
2. **Launch PLC and MES Containers**: Automatically build and start the background environments:
   ```bash
   sudo docker-compose up -d --build
   ```
3. **Start the Robot Simulator**: Activate your virtual environment and launch the visual simulator targeting the PLC container's IP:
   ```bash
   source venv/bin/activate
   PLC_IP=10.7.1.37 python robot_sim.py
   ```

*Note: If you plan to intercept and capture traffic (e.g., using a Monitor Server / IDS), please refer to the full documentation on how to configure an `iptables TEE` mirror port.*
