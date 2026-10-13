# Congestion: symptoms, causes and troubleshooting

## Symptoms
Network congestion happens when more traffic arrives at a link than it can carry. Router queues fill, so packets wait longer (latency rises, often several times normal) and, once the queue is full, are dropped (packet loss, TCP retransmissions). Jitter increases. Throughput per flow drops because TCP backs off. The combination of high latency, packet loss and many TCP retransmissions at the same time is the classic sign of congestion.

## Common causes
A large download or upload saturating the uplink; a non-responsive UDP stream (video, a backup tool) that does not slow down like TCP; many users sharing a slow link; a bottleneck link with small buffers; or a link failure that pushes traffic onto a smaller backup path.

## How to troubleshoot congestion
1. Confirm it: compare latency, loss and retransmissions with normal values for the same time of day.
2. Find the busiest flows and top talkers: which hosts and applications are using the bandwidth.
3. Check link utilization on the bottleneck link; near 100 percent confirms saturation.
4. Look for UDP streams that keep sending at a high rate while TCP flows slow down.
5. Remedies: schedule or rate-limit bulk transfers, apply QoS to prioritise interactive traffic, increase capacity, or fix the failed primary link if traffic was rerouted.
