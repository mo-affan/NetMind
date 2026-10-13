# Traffic anomalies and attacks

## What an anomaly is
An anomaly is traffic that looks different from normal for this network. It does not automatically mean an attack: a big backup, a software update or a new application can also look unusual. Anomalies are leads to investigate.

## Port scan
A port scan probes many ports on a host to find open services, usually before an attack. Signs: one source contacts a very large number of distinct destination ports in a short time, mostly TCP SYN packets, and the target answers closed ports with RST. The number of connections and of distinct destination ports jumps far above normal while bytes stay small. Response: identify the scanning source, check whether it is an authorised scanner, block it at the firewall, and review which ports on the target are actually open.

## SYN flood
A SYN flood sends many TCP SYN packets without completing the handshake, filling the server's table of half-open connections. Signs: many SYNs, few final ACKs, many different source addresses or ports. Defences: SYN cookies, rate limiting, firewalls.

## Ping flood and other floods
Floods send huge numbers of packets to exhaust bandwidth or CPU: packets per second rises sharply, usually from one or few sources, often with small packet sizes (ICMP echo). Block or rate-limit the source.

## Safe handling
Capture only on networks you own or are authorised to monitor. Treat findings as advisory and confirm before blocking traffic.
