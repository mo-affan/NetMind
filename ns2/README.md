# NS2 Simulation Module

Creates network problems on purpose, at known times, so NetMind's measurements and anomaly detection can be checked against known events.

**To run it in the college lab, follow [`docs/NS2_LAB_EXECUTION.md`](../docs/NS2_LAB_EXECUTION.md).**

## Status

| Status | State |
| --- | --- |
| Implemented: scenario and parser reviewed and fixed | Done |
| Validated: parser and pipeline tested on a sample trace | Done, on a synthetic sample (not NS2 output) |
| Executed: scenario run with NS2 | **Not yet.** Pending a run in the college lab |

## Files

| File | Purpose | Needs |
| --- | --- | --- |
| `netmind_scenario.tcl` | The NS2 scenario | NS2 (lab) |
| `check_trace.py` | Quick check of a trace: per-flow and per-second tables, drops per link, routes, 5 scenario checks | Python 3 standard library only (works in the lab) |
| `parse_trace.py` | Detailed tables and CSV | NetMind's requirements (pandas) |
| `results/` | Put real lab outputs here, one dated folder per run (committed as evidence) | |

Full analysis (database, anomaly detection, dashboard, Copilot): `python -m netmind ns2 <trace.tr>`. None of the Python tools need NS2 installed; they only read the trace file.

## Scenario (`netmind_scenario.tcl`)

5 nodes, 10 seconds, Distance Vector routing.

```
n0 (TCP source) \                 / n3 (sink)
                  n2 (router) ----        main link n2-n3: 1 Mb, 20 ms, DropTail queue of 10
n1 (UDP source) /    \           /
                      n4 (backup)          backup path n2-n4-n3: 1 Mb, 40 ms per link, cost 3 per link
```

| Time | Event | Expected effect |
| --- | --- | --- |
| 0.5 s | TCP/FTP starts n0 to n3 (window 6 packets) | Normal delay, no drops |
| 3.0 s | UDP/CBR 0.9 Mb/s burst n1 to n3 | Queue fills: delay up, packets dropped on n2-n3 |
| 6.0 s | UDP stops | Recovery |
| 7.0 s | Link n2-n3 down | Packets on it lost; DV reroutes via n4: delay up |
| 8.5 s | Link n2-n3 up | Back to the short path |

```bash
ns netmind_scenario.tcl          # writes netmind.tr and netmind.nam in the current folder
ns netmind_scenario.tcl run2     # writes run2.tr and run2.nam
```

### Changes made during review (2026-10-15)

- **TCP window limited to 6 packets.** With NS2's default window of 20, TCP alone would overflow the 1 Mb bottleneck and drop packets before 3 s, so the "normal" period would not be normal and the UDP congestion would not stand out.
- **Optional output name** as the first argument, so runs do not overwrite each other.
- **Timing messages** printed at each event, as evidence in the console output.
- **Node labels** for NAM, and the `finish` procedure prints where the files were written.

## Metric definitions (shared by all NetMind NS2 tools)

| Term | Definition |
| --- | --- |
| sent | a data packet's first `+` event at its own source node |
| delivered | an `r` event at its final destination node |
| dropped | a `d` event anywhere on its path, never delivered |
| in flight | neither delivered nor dropped when the trace ends; excluded from loss |
| loss % | dropped / (delivered + dropped), for packets sent in the window |
| delay | one-way: delivered time - sent time |
| throughput | bytes delivered in the window x 8 / window length |
| jitter | mean absolute change in delay between consecutive packets of the same flow |
| retransmission | a TCP packet sent with a sequence number that flow already sent |

Only data packets (`tcp`, `cbr`, `udp`, ...) are measured; TCP ACKs (`ack`) and routing messages (`rtProtoDV`) are skipped. Supported format: the standard wired trace written by `$ns trace-all`.

## Testing without NS2

- `tests/data/sample_ns2.tr` is a **synthetic** trace in NS2's wired format, made by `tests/make_ns2_sample.py` (a small Python queue model of this scenario, including ACK-clocked TCP with a window of 6 and retransmissions). It is not NS2 output.
- `tests/test_ns2.py` checks the parser's definitions on hand-written traces and the scenario's behaviour on the sample, and that `check_trace.py` agrees with the pandas parser.
- `tests/check_tcl_static.py` statically checks the .tcl file (balanced braces and quotes, known NS2 methods, defined variables, timeline). This is not a substitute for running it in NS2.
