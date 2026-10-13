# TCP (Transmission Control Protocol)

## What TCP does
TCP is a reliable, connection-oriented transport protocol (layer 4). It delivers a byte stream in order and without gaps. It uses sequence numbers to number every byte, acknowledgements (ACKs) to confirm receipt, and retransmission to resend data that was not acknowledged. Web (HTTP/HTTPS), SSH and email run over TCP.

## Three-way handshake
A TCP connection opens with three segments: the client sends SYN with its initial sequence number, the server answers SYN-ACK acknowledging it (ack = client seq + 1) and sending its own sequence number, and the client sends ACK. The time between the SYN and the SYN-ACK is one round-trip time (RTT), which is how NetMind measures latency from passive captures. A connection closes with FIN segments from both sides. A RST (reset) aborts a connection; a closed port answers a SYN with RST.

## Retransmissions and what they mean
If a segment is not acknowledged before the retransmission timeout (RTO), or the sender gets three duplicate ACKs, the segment is sent again with the same sequence number. Retransmissions are the main sign of packet loss on a TCP path. A few retransmissions are normal; a sudden increase, together with rising RTT, usually means congestion: router queues are full and packets are being dropped. Retransmissions on one host only can point to a bad cable, a weak Wi-Fi signal or a faulty NIC.

## Flow control
The receiver advertises a window: how many bytes it can accept. The sender never has more unacknowledged data than this window. A window of zero means the receiver is overwhelmed (a slow application), which looks like a stall even though the network is fine.

## Congestion control
TCP also limits itself to protect the network. It keeps a congestion window (cwnd). Slow start doubles cwnd every RTT until a threshold; congestion avoidance then grows it by one segment per RTT (additive increase). On loss, TCP cuts cwnd (multiplicative decrease, AIMD). So when a link is congested, every TCP flow on it slows down: throughput drops while latency and retransmissions rise.
