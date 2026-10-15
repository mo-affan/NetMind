# Progress log

Newest first.

| Date | Phase | What was done | Who |
| --- | --- | --- | --- |
| 2026-10-15 | NS2 | Reviewed and fixed the NS2 scenario and trace parser; consistent metric definitions; standard-library lab checker; lab execution guide. Status: implemented, validated on a synthetic sample, **not yet executed in NS2** | Affan |
| 2026-10-13 | 1-8 | First full implementation: capture (Scapy live/pcap, NS2 traces, demo traffic), traffic analyzer, performance metrics, topology with Dijkstra/LS/DV, SQLite storage, Isolation Forest anomaly detection with incidents, RAG knowledge base, Copilot (Claude/Ollama/offline), pipeline, CLI, REST API, Streamlit dashboard, Docker, 32 tests | Affan |
| 2026-10-13 | Setup | Repository created with module folders, NS2 scenario and trace parser, Review 1 documents | Affan |
| 2026-10-08 | Review 1 | Presented proposal (9 slides). Faculty suggested adding NS2; added NS2 Simulation Module | Both |
| 2026-10-07 | Proposal | Review 1 proposal document submitted | Both |

## Review 1 documents

In [`review-1/`](review-1/):

- `NetMind_Review1_Proposal.pdf`: the submitted proposal
- `NetMind_Review1_Presentation.pptx`: the Review 1 slides, with speaker notes
- `NetMind_Review1_Presentation_Guide.pdf`: project explanation and slide-by-slide script

## Changes since the proposal

- **NS2 Simulation Module added** (owner: Affan). A second data source next to live capture, used to create congestion and link failures at known times and to demonstrate Distance Vector routing.

## Design decisions

- **One record format for every source.** Live capture, pcap files, NS2 traces and demo traffic all become the same packet table, so every later module works on any source.
- **Latency is averaged per path.** Mixing a 3 ms gateway ping with a 45 ms web handshake made jitter look huge; grouping by (client, server, type) fixed that.
- **Isolation Forest plus a deviation check.** In normal traffic, loss is always 0, so the forest never learns to split on it and missed congestion. A robust z-score check (6+ units of normal spread) runs alongside and also explains which features stood out.
- **NS2 latency is one-way delay.** A simulator knows both send and receive times, so it measures delay directly instead of RTT.
- **Offline Copilot mode.** The demo works without an API key; Claude or a local Ollama model is used when available.

## Demo results (synthetic traffic, `python -m netmind demo`)

| Injected event | Time | Detected as | Key evidence |
| --- | --- | --- | --- |
| Congestion | 70-100 s | Network congestion | latency ~146 ms vs ~27 ms normal, loss ~9.5% vs 0 |
| Port scan | 120-128 s | Possible port scan, source 192.168.1.66 | ~311 destination ports per window vs ~10 |
| Ping flood | 150-158 s | Traffic flood, ICMP from 192.168.1.66 | ~550 packets/s vs ~41 |

No false alarms in normal traffic across three random seeds (one extra window flagged in one seed, right as congestion cleared, due to a late retransmission).

## NS2 status

| Status | State |
| --- | --- |
| Implemented (scenario and parser reviewed, fixes made) | Done 2026-10-15 |
| Validated (parser + pipeline on a sample trace) | Done 2026-10-15, on a **synthetic** trace, not NS2 output |
| Executed (scenario run in NS2) | **Pending**: to be run in the college lab, see `docs/NS2_LAB_EXECUTION.md` |

### NS2 review changes (2026-10-15)

- Scenario: TCP window limited to 6 packets (the default 20 would overflow the bottleneck before the UDP burst, making the "normal" period lossy); optional output name; timing messages; NAM node labels.
- Parser: loss now excludes packets still in flight at the end of the trace; jitter computed per flow (mixing flows inflated it); TCP retransmissions counted; route changes ordered by send time; link-down/up lines read when present; per-flow summary added. The NS2 pipeline's overall loss uses the same definition.
- Sample trace regenerated with ACK-clocked TCP (window 6), ACKs, retransmissions, and packet loss at the link failure.
- New: `ns2/check_trace.py` (standard library only, for the lab), `tests/check_tcl_static.py`, `docs/NS2_LAB_EXECUTION.md`, `ns2/results/` for lab evidence.

### Results on the synthetic sample (`tests/data/sample_ns2.tr`), not NS2 output

| Event | Time | Measured / detected |
| --- | --- | --- |
| Normal | 0.5-3 s | 0 drops, one-way delay ~42.5 ms |
| UDP burst on the 1 Mb bottleneck | 3-6 s | Loss 16-19% per second, delay ~111-118 ms; incident "Network congestion" |
| Link n2-n3 down | 7-8.5 s | 3 TCP segments lost and retransmitted; route n0-n2-n4-n3, delay ~112 ms; incident "Link failure and rerouting" |
| Link up | 8.5 s | Route back to n0-n2-n3 |

### Results from the real lab run

Not run yet. Fill in after the lab session: date, machine, Ubuntu and NS2 versions, the check_trace.py output, and the numbers above for the real trace.
