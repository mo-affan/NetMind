# About NetMind

## What NetMind measures
NetMind captures packets (Scapy) or reads NS2 simulation traces, classifies traffic into TCP, UDP, ICMP, DNS, HTTP and HTTPS, and computes per time window: packets per second, throughput, latency, jitter, packet loss, TCP retransmissions and connections. Latency comes from TCP SYN to SYN-ACK, ICMP echo request to reply, and DNS query to response pairs. Loss is estimated from TCP retransmissions and unanswered pings.

## How NetMind detects anomalies
Each time window becomes a feature vector: packets per second, average packet size, connections, connection duration, distinct destination ports, TCP/UDP ratio, bytes per second, latency, loss and retransmissions. An Isolation Forest trained on normal traffic gives an anomaly score from 0 to 1 (about 0.5 is normal, near 1 is very unusual). A second check measures how many units of normal spread each feature is from its normal value (deviation); a deviation of 6 or more marks the window anomalous. The features with the largest deviation explain why.

## NS2 simulation in NetMind
NS2 creates controlled problems at known times: a UDP burst that congests a 1 Mb bottleneck link and a link failure that forces Distance Vector routing to reroute through a backup node. NetMind reads the trace file and computes throughput, loss, one-way delay and jitter, so detection can be checked against known events.

## Network health score
NetMind gives every time window a health score from 0 to 100. A window starts at 100 and loses up to 40 points when latency rises above its normal level (the full 40 at four times normal), up to 40 points for packet loss (the full 40 at 5% loss) and 20 points when the anomaly detector flagged it. The run's score is the average of its windows: 90 or more is Good, 70 to 90 is Fair and below 70 is Poor. A low score says how much the users felt the problem; the incidents say what the problem was.

## Hosts, services and connection outcomes
NetMind lists every host it saw with its scope (private, public, loopback), its role (client, server, client and server, likely scanner) and the services it answered on, such as TCP 443 (HTTPS), DNS 53 or ICMP echo. Every TCP connection attempt is followed from its SYN: established when the server answered SYN-ACK, refused when it answered RST, unanswered when nothing came back, and reset when an established connection was aborted with RST. Many refused or unanswered attempts from one host to many different ports is the signature of a port scan, so such a host is marked as a likely scanner. For DNS, NetMind matches each query to its response by transaction id and reports lookups, unanswered lookups, response time and the most-queried domain names.

## Limits
NetMind's topology shows hosts seen communicating, not physical cabling. HTTPS content is encrypted, so only headers and timing are analysed. The Copilot only explains and recommends; it never changes the network.
