# UDP and ICMP

## UDP (User Datagram Protocol)
UDP is a connectionless transport protocol. It sends datagrams with no handshake, no acknowledgements, no retransmission and no congestion control. It is fast and simple, used by DNS, video and voice streaming, online games and DHCP. Because UDP does not slow down when the network is congested, a heavy UDP stream can take bandwidth from TCP flows sharing the same link: TCP backs off, UDP does not. Loss on UDP is not repaired by the protocol; the application has to cope.

## TCP vs UDP
TCP: reliable, ordered, connection-oriented, flow and congestion control, more overhead. UDP: unreliable, unordered, connectionless, minimal 8-byte header, lower delay. Choose TCP when every byte must arrive (files, web pages); UDP when timeliness matters more than completeness (live media, DNS lookups).

## ICMP and ping
ICMP (Internet Control Message Protocol) carries error and control messages for IP, for example destination unreachable, time exceeded (used by traceroute) and echo request / echo reply (used by ping). Ping sends echo requests (type 8) and measures the time until the echo reply (type 0): that is the round-trip time. Requests without replies indicate packet loss, a host that is down, or a firewall blocking ICMP.

## Ping flood
A ping flood sends ICMP echo requests at a very high rate (hundreds or thousands per second) to one host. Symptoms: packets per second jumps far above normal, average packet size drops (ping packets are small, about 84 bytes), and most traffic is ICMP from one source to one destination. It wastes bandwidth and CPU on the target. Response: identify the source address, rate-limit or block ICMP from it at the gateway or firewall.
