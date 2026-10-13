# OSI model, TCP/IP and IP addressing

## OSI and TCP/IP layers
The OSI model has seven layers: physical, data link, network, transport, session, presentation, application. The TCP/IP model used on the internet groups them into four: link (Ethernet, Wi-Fi), internet (IP, ICMP), transport (TCP, UDP) and application (DNS, HTTP). NetMind captures packets at the link layer and analyses the network (IP, ICMP), transport (TCP, UDP) and application (DNS, HTTP) layers.

## IPv4 addressing and subnets
An IPv4 address is 32 bits written as four numbers (192.168.1.10). A subnet mask or CIDR prefix (/24) says which part is the network and which part the host. 192.168.1.0/24 holds hosts 192.168.1.1 to 192.168.1.254. Private ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) are used inside LANs; the gateway (often .1) forwards traffic to other networks. Classful addressing (A, B, C) was replaced by classless CIDR to use addresses efficiently.

## NAT and IPv6
NAT (Network Address Translation) lets many private hosts share one public IP: the router rewrites source addresses and ports on the way out and maps replies back. IPv6 uses 128-bit addresses written in hexadecimal (2001:db8::1), removing the need for NAT, and replaces ARP with neighbour discovery.
