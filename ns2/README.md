# NS2 Simulation Module

Creates network problems on purpose, at known times, so NetMind's measurements and anomaly detection can be checked.

## Scenario (`netmind_scenario.tcl`)

5 nodes, 10 seconds, Distance Vector routing.

```
n0 (TCP source) \                 / n3 (sink)
                  n2 (router) ----        main link n2-n3: 1 Mb, 20 ms, DropTail queue of 10
n1 (UDP source) /    \           /
                      n4 (backup)          backup path n2-n4-n3: 1 Mb, 40 ms per link
```

| Time | Event | Expected effect |
| --- | --- | --- |
| 0.5 s | TCP/FTP starts n0 to n3 | Normal delay, no loss |
| 3.0 s | UDP/CBR 0.9 Mb burst n1 to n3 | Queue fills: delay up, packets dropped |
| 6.0 s | UDP stops | Recovery |
| 7.0 s | Link n2-n3 down | DV reroutes via n4: delay up |
| 8.5 s | Link n2-n3 up | Back to short path |

## Run

```bash
ns netmind_scenario.tcl            # writes netmind.tr and netmind.nam
nam netmind.nam                    # animation
python3 parse_trace.py netmind.tr  # per-second metrics, saved to netmind_metrics.csv
python3 parse_trace.py netmind.tr --window 0.5
```

## Parser output

One row per flow per time window: packets sent, packets dropped, loss %, throughput (Mbps), average delay (ms) and jitter (ms).

Delay for a packet is the time it reaches the destination node (`r` event) minus the time it left the source node (`+` event). ACKs and routing packets are ignored.

## Status

- `parse_trace.py`: tested on a sample trace in NS2 format.
- `netmind_scenario.tcl`: written in standard ns-2 syntax, not yet run on a real NS2 install. Run it once and record the result in `docs/PROGRESS.md`.
