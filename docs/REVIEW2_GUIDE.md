# NetMind: Review 2 guide

How NetMind works, module by module, with the exact algorithms and formulas the code uses, followed by viva questions. Every number quoted here comes from the synthetic demo (`python -m netmind demo`, seed 7) or the synthetic NS2 sample trace; say so if asked.

## 1. Architecture

```
Input (M1)               Analysis                          Storage        Use
-----------              --------                          -------        ---
synthetic demo ─┐                       ┌ M4 performance ┐
pcap file ──────┼> packet ─> M2 traffic ┼ M5 topology    ┼> M6 SQLite ─┬> M9 dashboard
live capture ───┤  records   analyzer   └ M3 anomaly ────┘   (runs)    ├> REST API
NS2 trace ──────┘                          └> incidents                └> M8 Copilot <── M7 RAG
```

One design rule ties it together: **every input becomes the same packet-record table** (`netmind/capture/records.py`: time, src, dst, ports, protocol, length, TCP flags/seq/ack, ICMP type/id/seq, DNS id/query-or-response). Every later module works on that table, so it does not matter whether the traffic was captured, read from a file, simulated in NS2 or generated.

`netmind/pipeline.py` runs the modules in order and saves one **run** per analysis.

## 2. Modules

### M1 Input (`netmind/capture/`)
- **Synthetic demo** (`synthetic.py`): three clients browsing (DNS lookup, TCP handshake, HTTP/HTTPS transfer, FIN), pinging the gateway every 2 s; injected congestion (RTT x4, 7% loss with retransmissions, 70-100 s), port scan (1000 SYNs from 192.168.1.66, 120-128 s), ping flood (250 echo/s, 150-158 s). Deterministic by seed. Labelled "synthetic" everywhere.
- **Scapy** (`sniffer.py`): `sniff()` for live capture (needs admin rights and Npcap on Windows), `rdpcap()` for files.
- **NS2** (`ns2.py`): reads the wired trace format `event time from to type size flags fid src dst seq pktid`.

### M2 Traffic analyzer (`netmind/analyzer/traffic.py`)
- Protocol: transport from the IP header (TCP/UDP/ICMP); application from well-known ports (53 DNS, 80 HTTP, 443 HTTPS) and the DNS layer.
- **Flow** = 5-tuple (src IP, src port, dst IP, dst port, protocol), made direction-independent by ordering the two endpoints, so request and reply belong to one flow.
- Outputs: protocol distribution, flows (packets, bytes, duration), top talkers.

### M4 Performance (`netmind/performance/metrics.py`)
| Metric | Formula / method |
| --- | --- |
| Latency (RTT) | SYN at t1, SYN-ACK at t2 with ack = seq+1 -> RTT = t2 - t1; same for ICMP echo (matching id and seq) and DNS (matching transaction id). Averaged per path (client, server, type), then across paths |
| Throughput | bytes x 8 / window seconds (Mb/s) |
| Utilization | throughput / link capacity (default 100 Mb/s) |
| Packet loss | (retransmitted TCP data segments + unanswered pings) / (TCP data segments + pings). A retransmission = same direction, ports and sequence number seen again |
| Jitter | mean of abs(RTT_i - RTT_i-1) for consecutive samples **on the same path** |
| Traffic rate | packets / window seconds |

Why per path: a 3 ms gateway ping and a 45 ms web handshake are different paths. Mixing them made jitter look like about 20 ms on a calm network; per path it is about 4-5 ms.

### M5 Topology and routing (`netmind/topology/graph.py`)
- Graph (NetworkX): nodes = hosts seen; edge = the two hosts exchanged packets; edge weights: `latency` (median measured RTT) and `hops` (1).
- **Dijkstra**: shortest path on either weight.
- **Link State** (OSPF idea): every node knows the full graph and runs Dijkstra -> next hop and cost per destination.
- **Distance Vector** (RIP idea, Bellman-Ford): each round, every node takes its neighbours' tables from the previous round and sets cost(dst) = min over neighbours n of link(u,n) + cost_n(dst); repeat until nothing changes. The code reports the number of rounds. Tests check LS and DV give identical costs, and that DV reroutes when a link is removed.
- Limitation: it is a logical map of who talked to whom, not physical cabling.

### M3 Anomaly detection (`netmind/anomaly/`)
- Windows of 2 s (0.5 s for NS2). **10 features per window**: packets/s, average packet size, connections (distinct flows), average connection duration, distinct destination ports, TCP/(UDP+1) ratio, bytes/s, latency, loss %, retransmissions.
- **Baseline**: the first `train_until` seconds (demo: 60 s), or by default the first 30% of windows, at least 8 windows (16 s). Less than that: detection is **skipped** and reported as "not enough traffic", never as "normal".
- **Isolation Forest** (200 trees, scikit-learn): features are log1p-scaled and standardised; the score is reported on the 0-1 scale of Liu et al. (2008), so about 0.5 is normal and close to 1 is very unusual. scikit-learn's `score_samples` returns the negative, so the sign is flipped. Threshold = 99th percentile of the baseline's own scores + 0.03 + 0.25/sqrt(baseline windows).
- **Deviation check**: robust z = (value - baseline median) / (1.4826 x MAD), with a minimum spread per feature (e.g. 0.5% for loss, 3 ms for latency).
- **Decision**: anomalous if z >= 6 for some feature, OR (forest score > threshold AND some z >= 4).
- Why both: Isolation Forest only splits on values it has seen. Loss is always 0 in normal traffic, so the forest alone could not isolate a congested window (it missed congestion in testing). The deviation check catches it and also says which features stood out. Requiring a z of 4 or more behind a forest flag, a stricter threshold for short baselines and a 16 s minimum baseline cut false alarms on normal-only synthetic traffic (5 capture lengths x 10 seeds) from 18 flagged windows to 3 (out of about 1,350-1,410 windows).
- **Incidents** (`episodes.py`): consecutive flagged windows (1-window gap allowed) become one incident. It is typed from its strongest features (port scan: many destination ports; congestion: latency/loss/retransmissions; flood: high packets/s with small packets; NS2: reroute when a route change happens inside it). The source/destination are taken from requests (SYN, echo request, DNS query), not replies.

### M6 Storage (`netmind/storage/db.py`)
SQLite file `data/netmind.db`. Table `runs` (name, source, time, JSON summary) and per-run tables: metrics, anomalies, incidents, nodes, links, flows, protocols, rtt. New columns from a different source (e.g. NS2's `dropped`) are added with `ALTER TABLE`.

### M7 RAG (`netmind/rag/`)
- Knowledge base: 9 markdown documents written for the project (TCP, UDP/ICMP, DNS/HTTP, IP/OSI, routing, performance, congestion, attacks, NetMind itself).
- Chunking: by `##` section, long sections split at sentence boundaries (about 140 words): 36 chunks.
- Embeddings: **TF-IDF** (1-2 word n-grams) by default, so it works offline with no model download; **Sentence Transformers** (all-MiniLM-L6-v2) if installed. Search: cosine similarity, with FAISS if installed, else NumPy. Top-k = 4.

### M8 Copilot (`netmind/copilot/copilot.py`)
- Prompt = **question + network state** (summary, overall metrics, baseline, latest window, routes) **+ incidents** (type, time, score, standout features with normal values, busiest source/destination) **+ retrieved knowledge** [1]..[4]. `python -m netmind ask "..." --show-prompt` prints it.
- Backends: offline (default; rule-based answer built from the incidents and the top knowledge chunks), Claude API, or local Ollama. Falls back to offline if the LLM is unreachable.
- Concept questions ("What is jitter?") are answered from the knowledge base; data questions ("Why is my network slow?") from incidents.
- Advisory only: it never changes, blocks or configures anything.

### M9 Dashboard, API, CLI
- Streamlit: headline metrics, packets/s / latency / loss / anomaly score over time with incidents shaded, incident cards, protocol chart, Copilot chat, topology with Dijkstra path and LS vs DV tables, raw tables. Can run the demo or analyse an uploaded pcap/NS2 trace.
- FastAPI: `/health`, `/runs`, `/runs/{id}` and its metrics, anomalies, incidents, protocols, flows, topology, `/path`, `/routing`, `POST /ask`.
- CLI: `python -m netmind demo | pcap | capture | ns2 | runs | report | ask | routes | dashboard | api`.

### NS2 module (`ns2/`)
Scenario: 5 nodes; TCP n0 to n3 (window 6); UDP CBR 0.9 Mb/s n1 to n3 from 3 to 6 s on a 1 Mb bottleneck with a queue of 10; link n2-n3 down from 7 to 8.5 s; Distance Vector reroutes through n4. **Status: implemented and validated on a synthetic sample trace; not yet run in NS2** (lab guide: `docs/NS2_LAB_EXECUTION.md`).

## 3. Results to quote (synthetic data)

| Scenario | NetMind output |
| --- | --- |
| Demo congestion, 70-100 s | Latency 146 ms vs 26.5 ms normal; loss 9.5% vs 0; incident "Network congestion" |
| Demo port scan, 120-128 s | 311 destination ports per window vs 10; "Possible port scan" from 192.168.1.66 to 192.168.1.10 |
| Demo ping flood, 150-158 s | 551 packets/s vs 41, average packet size 104 vs 660 bytes; "Traffic flood", ICMP from 192.168.1.66 |
| NS2 sample, 3-6 s | Loss about 20%, delay 118 ms vs 42 ms; "Network congestion" |
| NS2 sample, 7-8.5 s | Route n0-n2-n4-n3, delay 113 ms; 3 TCP retransmissions; "Link failure and rerouting" |
| Detection check, 10 seeds | All injected events found; under 0.5% of normal windows flagged |

## 4. Viva questions

**Is this a networks project or an AI project?** Networking first: capture, protocol analysis, RTT/loss/jitter measurement, flows, topology, Dijkstra, Link State, Distance Vector and NS2 are the core. The ML and LLM only interpret what those modules measured.

**How do you measure latency without sending anything?** From pairs already in the traffic: a TCP SYN and the SYN-ACK whose ack number is the SYN's sequence + 1, an ICMP echo request and reply with the same id and sequence, a DNS query and response with the same transaction id.

**How can you know packets were lost if you never saw them?** We infer it. TCP resends lost data with the same sequence number, so a repeated data segment is a retransmission; an echo request without a reply is a lost ping. In NS2 the trace records drops directly (`d` events).

**What is jitter and why compute it per path?** Variation in delay between consecutive packets. Different paths have different base delays, so mixing them measures the difference between paths, not variation.

**What is a flow?** Packets sharing the 5-tuple (src IP, src port, dst IP, dst port, protocol); we merge both directions into one flow.

**Why Isolation Forest?** It is unsupervised (no labelled attacks needed), fast, and isolates points that are few and different: an anomalous window is separated from the rest in fewer random splits.

**Why the extra deviation check?** Isolation Forest cannot split on a feature that never varied in training (loss = 0), so it missed congestion. The deviation check catches it and explains the incident. Requiring a z of 4 or more behind forest flags reduced false alarms.

**How do you avoid false alarms on a short capture?** A minimum baseline of 8 windows (16 s); a stricter forest threshold for short baselines; and below the minimum, detection is skipped and reported as such.

**What is the anomaly score?** The Isolation Forest score on a 0-1 scale: 2^(-average path length / c(n)). About 0.5 means normal; close to 1 means very easy to isolate.

**Dijkstra vs Bellman-Ford?** Dijkstra picks the closest unfinished node each step and needs non-negative weights; Bellman-Ford relaxes all edges repeatedly, handles negative weights and is the basis of Distance Vector.

**Link State vs Distance Vector?** LS: every router floods link states, knows the whole map, runs Dijkstra (OSPF). DV: routers only exchange distance tables with neighbours (RIP); simpler but slower to converge, and can suffer count-to-infinity.

**What does NS2 add?** Problems at known times (congestion, link failure) in a repeatable network, so we can check that NetMind's measurements and detection match the truth, and see Distance Vector rerouting.

**What is RAG?** Retrieval-Augmented Generation: before answering, retrieve the most relevant knowledge chunks and put them in the prompt, so the answer rests on correct theory and can cite it.

**Why TF-IDF and not only embeddings?** It works offline with no model download; Sentence Transformers can be switched on for semantic matching.

**What if the LLM is wrong?** Measurements come from the database, not the LLM; the prompt tells it to use only the given data and cite sources; the Copilot is advisory; the offline mode is deterministic.

**What about HTTPS?** Content is encrypted; we use headers, ports, sizes and timing only.

**Limitations?** Synthetic demo data; topology is logical; passive loss is an estimate; the TCL scenario still has to be run in NS2; thresholds were tuned on synthetic traffic and should be checked on real captures.
