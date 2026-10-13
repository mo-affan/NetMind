# Network performance metrics and QoS

## Latency
Latency (delay) is the time for data to travel; round-trip time (RTT) is there and back. Components: propagation delay (distance), transmission delay (packet size / bandwidth), processing delay, and queuing delay (waiting in router buffers). Queuing delay is the part that grows during congestion. Rough guide: under 30 ms is good on a LAN or nearby servers, 100 ms or more is noticeable in interactive use, and a sudden multiple of the normal value matters more than the absolute number.

## Throughput and bandwidth
Bandwidth is a link's capacity (for example 100 Mbps). Throughput is the data actually delivered per second, throughput = bytes x 8 / time. Utilization = throughput / capacity. Throughput below the capacity with high loss or latency means a bottleneck somewhere on the path.

## Packet loss
Packet loss is the percentage of packets that never arrive. Causes: full router queues (congestion), errors on the physical link, wireless interference, or misbehaving devices. Even 1 to 2 percent loss noticeably slows TCP, because every loss makes TCP retransmit and shrink its congestion window. A passive capture cannot see lost packets directly; loss is estimated from TCP retransmissions or measured with ping.

## Jitter
Jitter is the variation in delay between packets. It hurts voice and video more than file transfers. High jitter usually comes from queues that fill and drain, i.e. congestion or bursty competing traffic.

## Quality of Service (QoS)
QoS parameters are latency, jitter, packet loss and throughput. QoS mechanisms (priority queues, traffic shaping, rate limiting) give important traffic, such as voice, better treatment when a link is busy.
