# Progress log

Newest first.

| Date | Phase | What was done | Who |
| --- | --- | --- | --- |
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

## NS2 sample results (`tests/data/sample_ns2.tr`)

| Event | Time | Detected as |
| --- | --- | --- |
| UDP burst on the 1 Mb bottleneck | 3-6 s | Congestion: loss ~42%, delay ~120 ms vs ~42 ms |
| Link n2-n3 down | 7-8.5 s | Link failure and rerouting: path n0-n2-n4-n3, delay ~111 ms |
