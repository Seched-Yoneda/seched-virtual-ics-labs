# Lab Configuration

| Lab name<br>(Github repository name) | ID | Role | OS | Internal Network<br>Static IP Address | Addtional NW Interface for development | Remarks |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| security-lab-manager | A.1 | Lab Host | Windows11 | Dynamic IP | | Main PC hosting all |
| | A.2 | Management Proxy | WSL Ubuntu | Dynamic IP on Win11 | | |
| vuln-test-lab | B.1 | VirtualBox DHCP server | | 10.7.0.2 | | IP assigned using VBoxMgr |
| | B.2 | Security Assessment | Kali Linux 2025.4 | 10.7.0.3 | HostOnly Adapter 192.168.56.7 | IP assigned manually |
| | C.3 | Vulnerable Server | Ubuntu16(metaploitable2) | 10.7.0.x | | IP assigned by DHCP. |
| enip-lab | 1.1 | VirtualBox DHCP server | VirtualBox | 10.7.1.2 | | IP assigned using VBoxMgr |
| | 1.2 | Security Assessment | Kali Linux 2025.4 | 10.7.1.3 | HostOnly Adapter 192.168.56.7 | The ame OS as ID 0.2 |
| | 1.3 | Monitor Server | Ubntu24.04 server | 10.7.1.32 | NAT with portforwarding<br>127.0.01 port 2232->port22 | |
| | 1.4 | FA DockerHost | Ubuntu24.04 desktop | 10.7.1.36 | NAT with portforwarding<br>127.0.01port 7136->port22 | IP assigned manually |
| | 1.5 | EtherNet/IP Server PLC | Docker using macvlan | 10.7.1.37 | | IP assigned manually |
| | 1.6 | EtherNet/IP Client MES | Docker using macvlan | 10.7.1.38 | | IP assigned manually |
| | 1.7 | Docker host interface for macvlan | | 10.7.1.39 | | IP assigned manually |
| modbus-lab | 2.1 | VirtualBox DHCP server | VirtualBox | 10.7.2.2 | | IP assigned using VBoxMgr |
| | 2.2 | Security Assessment | Kali Linux 2025.4 | 10.7.2.3 | HostOnly Adapter 192.168.56.7 | The same OS as ID 0.2<br>IP changed manually |
| | 2.3 | Monitor Server | Ubntu 24.04 server | 10.7.2.32 | NAT with portforwarding<br>127.0.01 port 2232->port22 | The same OS as ID 1.3<br>IP changed manually |
| | 2.4 | Plant DockerHost | Ubuntu 24.04 desktop | 10.7.2.36 | NAT with portforwarding<br>127.0.01 port 7236->port22 | IP assigned manually |
| | 2.5 | Modbus Server PLC for BPCS | Docker using macvlan | 10.7.2.37 | | IP assigned manually |
| | 2.6 | Modbus Client SCADA | Docker using macvlan | 10.7.2.39 | | IP assigned manually |
| bacnet-lab | 3.1 | VirtualBox DHCP server | VirtualBox | 10.7.3.2 | | IP assigned using VBoxMgr |
| | 3.2 | Security Assessment | Kali Linux 2025.4 | 10.7.3.3 | HostOnly Adapter 192.168.56.7 | The Same OS as ID 0.2 |
| | 3.3 | Monitor Server | Ubuntu 24.04 server | 10.7.3.32 | NAT with portforwarding<br>127.0.01 port 2232->port22 | The same OS as ID 1.3<br>IP changed manually |
| | 3.4 | Bacnet Server | Ubuntu 18.04 desktop | 10.7.3.36 | NAT with portforwarding<br>127.0.01 port 7336->port22 | Antigravity Unsuported. |
| | 3.5 | Bacnet Client | Ubuntu 18.04 desktop | 10.7.3.37 | NAT with portforwarding<br>127.0.01 port 7337->port22 | Antigravity Unsuported. |
| monitor-server | | | | | | Repo.name. for 1.3 monitor-server |
