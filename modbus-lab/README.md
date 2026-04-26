# modbus-lab

This repository contains the source code and configuration files for setting up a simulated plant environment using Modbus communication on an Ubuntu 24.04 Server. It is designed for cybersecurity monitoring and simulation exercises in Industrial Control Systems (ICS).

## Environment Overview

The simulation environment consists of the following components containerized using Docker:

| Type | Purpose | Implementation Format |
|---|---|---|
| Modbus Server | PLC for BPCS (Basic Process Control System) | Docker (C, `libmodbus`) |
| Modbus Client | OCS (Operator Control System) / SCADA | Docker (Python, `Flask`, `pymodbus`) |

## Setup Instructions

For full step-by-step instructions on how to prepare the VirtualBox host environment, configure networking, and install Docker, please refer to the detailed setup guides:
- [Plant Environment Setup Procedure using Modbus Communication (English)](Plant_Environment_Setup_Procedure_using_Modbus_Communication.md)
- [Modbus通信を用いたプラント環境構築手順 (Japanese)](Modbus通信を用いたプラント環境構築手順.md)

### Quick Start

Once your Docker host is prepared and network interfaces are configured as per the guide, you can start the environment using Docker Compose.

1. Clone this repository to your Docker host.
2. Navigate to the project directory.
3. Build and start the containers:

```bash
sudo docker compose build
sudo docker compose up -d
```

*Note: If you are using the Macvlan network driver (as described in the setup guide), ensure your host's network interface is set to promiscuous mode.*

## Accessing the SCADA HMI

Once the containers are running, you can access the SCADA web interface from a browser on a machine within the same network (e.g., Kali Linux).

```
http://<SCADA-Container-IP>:5000
```
*(Based on the configuration guide, the default IP is `10.7.2.39`)*

## Network Traffic Mirroring (For IDS)

The detailed setup guide includes instructions on how to configure `iptables TEE` mirroring for Modbus traffic (TCP port 502) to a monitor server (IDS) for packet capture and analysis. Please see **Section 6** of the documentation for more information.
