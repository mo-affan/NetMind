# NetMind

**AI-Powered Network Intelligence and LLM Network Copilot**

Computer Networks Lab (BCSE308P) project, VIT Vellore.

| Member | Reg. no. |
| --- | --- |
| Mohammed Affan | 24BAI0014 |
| Hardik | 24BCI0017 |

## What it does

Network monitoring tools show raw numbers (latency, packet loss, connections) but leave the interpretation to the user. NetMind works in three steps:

1. **Measure.** Capture traffic, identify protocols (TCP, UDP, ICMP, DNS, HTTP, HTTPS) and calculate latency, throughput, packet loss, jitter and utilization per time window.
2. **Detect.** An Isolation Forest model, plus a deviation-from-normal check, flags time windows that look unusual and groups them into incidents (congestion, port scan, flood, link failure).
3. **Explain.** An LLM Copilot uses RAG over a networking knowledge base to explain the likely cause in plain English. It only advises and never controls the network.

Traffic comes from three sources that all feed the same pipeline: **live capture** with Scapy, **pcap files** (e.g. from Wireshark), and **NS2 simulation** traces, where congestion and link failures are created on purpose so detection can be checked against known events. A **synthetic demo** with three known problems is built in.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate              # Windows   (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt

python -m netmind demo              # analyse demo traffic: congestion, port scan, ping flood
python -m netmind ask "Why is the network slow?"
python -m netmind dashboard         # opens the dashboard in your browser
```

## Commands

| Command | What it does |
| --- | --- |
| `python -m netmind demo` | Generate 180 s of traffic with congestion (70-100 s), a port scan (120-128 s) and a ping flood (150-158 s), analyse it, save `data/demo.pcap` |
| `python -m netmind capture --duration 60` | Live capture and analyse. Needs admin rights (Windows: run the terminal as Administrator, install [Npcap](https://npcap.com)) |
| `python -m netmind interfaces` | List capture interfaces (use with `--iface`) |
| `python -m netmind pcap file.pcap` | Analyse a Wireshark / tcpdump capture |
| `python -m netmind ns2 ns2/netmind.tr` | Analyse an NS2 trace |
| `python -m netmind runs` | List saved runs |
| `python -m netmind report [--run N]` | Metrics table and incidents of a run |
| `python -m netmind ask "question" [--run N]` | Ask the Copilot (`--show-prompt` shows the RAG prompt) |
| `python -m netmind routes --from A --to B` | Dijkstra path, Link State vs Distance Vector routing tables |
| `python -m netmind dashboard` | Streamlit dashboard |
| `python -m netmind api` | REST API, docs at http://127.0.0.1:8000/docs |

## Copilot LLM backends

| Backend | How to enable | Notes |
| --- | --- | --- |
| Claude (Anthropic API) | `set ANTHROPIC_API_KEY=...` (Mac/Linux: `export`) | Model via `NETMIND_LLM_MODEL` (default `claude-haiku-5-5`) |
| Ollama (local, free) | Install [Ollama](https://ollama.com), `ollama pull llama3.2` | Model via `NETMIND_OLLAMA_MODEL` |
| Offline | Nothing to set | Rule-based explanation from the same evidence and knowledge; used automatically when no LLM is available |

The prompt combines the four inputs from the proposal: the question, the network state, the anomaly incidents and the retrieved knowledge.

## Architecture

```
Live capture (Scapy) ─┐
pcap file ────────────┼─> packet records ─> Traffic Analyzer ─┬─ Performance Analyzer ─┐
NS2 trace ────────────┘                     (protocols, flows) ├─ Topology + Routing ───┼─> SQLite ─┬─> Dashboard
                                                                └─ Anomaly Detection ────┘   state   ├─> REST API
                                                                                                     └─> Copilot <─ RAG knowledge base
```

## Repository layout

| Path | Module | Owner |
| --- | --- | --- |
| `netmind/capture/` | M1 Packet capture: Scapy live/pcap (`sniffer.py`), NS2 traces (`ns2.py`), demo traffic (`synthetic.py`), common record format (`records.py`) | Hardik (NS2: Affan) |
| `netmind/analyzer/` | M2 Traffic analyzer: protocol distribution, flows (5-tuple), top talkers | Hardik |
| `netmind/anomaly/` | M3 Anomaly detection: window features, Isolation Forest, incidents | Affan |
| `netmind/performance/` | M4 Performance: RTT (TCP handshake, ping, DNS), throughput, loss, jitter, utilization | Affan |
| `netmind/topology/` | M5 Topology graph, Dijkstra, Link State and Distance Vector simulation | Hardik |
| `netmind/storage/` | M6 SQLite network state database | Hardik |
| `netmind/rag/` | M7 RAG: knowledge base (`knowledge/*.md`), chunking, embeddings, vector search | Affan |
| `netmind/copilot/` | M8 LLM Network Copilot | Affan |
| `netmind/dashboard/` | M9 Streamlit dashboard | Hardik (lead) |
| `netmind/pipeline.py`, `api.py`, `__main__.py` | Integration: pipeline, REST API, command line | Both |
| `ns2/` | NS2 scenario (`netmind_scenario.tcl`) and standalone trace parser | Affan |
| `tests/` | pytest suite, NS2 sample trace | Both |
| `docs/` | Review documents and progress log | Both |

## How the main numbers are calculated

- **Latency:** time between a request and its reply: TCP SYN to SYN-ACK (matched by sequence number), ICMP echo request to reply, DNS query to response. Averaged per path so a fast gateway ping does not hide a slow web server.
- **Packet loss:** a passive capture cannot see lost packets, so loss = (TCP retransmissions + unanswered pings) / (data segments + pings).
- **Jitter:** mean absolute difference between consecutive RTTs on the same path.
- **Anomaly score:** Isolation Forest score on the 0-1 scale of the original paper (~0.5 normal, near 1 very unusual), trained on the first part of the capture. A window is also flagged when a feature is 6+ units of normal spread away from its normal value, which catches problems in features that never varied during training (e.g. loss).

## NS2

See [`ns2/README.md`](ns2/README.md). In short (Ubuntu or WSL):

```bash
sudo apt install ns2 nam
cd ns2 && ns netmind_scenario.tcl && nam netmind.nam
cd .. && python -m netmind ns2 ns2/netmind.tr
```

## Tests

```bash
pytest
```

## Docker

```bash
docker build -t netmind .
docker run -p 8501:8501 netmind      # dashboard at http://localhost:8501
```

## Development phases

| Phase | Work | Status |
| --- | --- | --- |
| 0 | Proposal and Review 1 | Done |
| 1 | Packet capture and traffic analysis | Done |
| 2 | Performance analysis | Done |
| 3 | Topology and routing | Done |
| 4 | ML anomaly detection | Done |
| 5 | RAG knowledge engine | Done |
| 6 | LLM Copilot | Done |
| 7 | Dashboard | Done |
| 8 | Integration, testing, Docker | Done |
| NS2 | Simulation scenario, trace analysis | Done (scenario to be run on a real NS2 install) |

See [`docs/PROGRESS.md`](docs/PROGRESS.md) for the dated log.

## Ethics

Only capture traffic on networks you own or have permission to monitor. The Copilot is advisory and never changes the network.
