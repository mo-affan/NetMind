# NetMind

**AI-Powered Network Intelligence and LLM Network Copilot**

Computer Networks Lab (BCSE308P) project, VIT Vellore.

| Member | Reg. no. |
| --- | --- |
| Mohammed Affan | 24BAI0014 |
| Hardik | 24BCI0017 |

## What it does

Network monitoring tools show raw numbers (latency, packet loss, connections) but leave the interpretation to the user. NetMind works in three steps:

1. **Measure.** Capture traffic, identify protocols (TCP, UDP, ICMP, DNS, HTTP) and calculate latency, throughput, packet loss and jitter.
2. **Detect.** An Isolation Forest model flags traffic that looks different from normal.
3. **Explain.** An LLM Copilot uses RAG over a networking knowledge base to explain the likely cause in plain English. It only advises and never controls the network.

Traffic comes from two sources: **live capture** with Scapy and **NS2 simulation**, where congestion and link failures are created on purpose so detection can be tested against known events.

## Architecture

```
Live Capture (Scapy) ─┐                 ┌─ Performance Analyzer ─┐                ┌─ RAG Engine ─┐
                      ├─ Traffic ───────┼─ Topology + Routing ───┼─ State DB ─────┤              ├─ Dashboard
NS2 Simulation ───────┘  Analyzer       └─ ML Anomaly Detection ─┘  (SQLite)      └─ LLM Copilot ┘
```

## Repository layout

| Path | Contents | Owner |
| --- | --- | --- |
| `netmind/capture/` | M1 Packet capture (Scapy) | Hardik |
| `netmind/analyzer/` | M2 Traffic analyzer: protocols, flows | Hardik |
| `netmind/performance/` | M4 Performance analyzer: latency, throughput, loss, jitter | Affan |
| `netmind/topology/` | M5 Topology graph and routing (NetworkX, Dijkstra) | Hardik |
| `netmind/storage/` | M6 Network state database (SQLite) | Hardik |
| `netmind/anomaly/` | M3 ML anomaly detection (Isolation Forest) | Affan |
| `netmind/rag/` | M7 RAG knowledge engine | Affan |
| `netmind/copilot/` | M8 LLM Network Copilot | Affan |
| `netmind/dashboard/` | M9 Dashboard (Streamlit) | Hardik (lead) |
| `ns2/` | NS2 simulation scenario and trace parser | Affan |
| `tests/` | Tests | Both |
| `docs/` | Review documents, presentations and progress log | Both |

## Development phases

| Phase | Work | Status |
| --- | --- | --- |
| 0 | Proposal and Review 1 | Done |
| 1 | Packet capture and traffic analysis | Not started |
| 2 | Performance analysis | Not started |
| 3 | Topology and routing | Not started |
| 4 | ML anomaly detection | Not started |
| 5 | RAG knowledge engine | Not started |
| 6 | LLM Copilot | Not started |
| 7 | Dashboard | Not started |
| 8 | Integration, testing, Docker | Not started |
| NS2 | Simulation scenario and trace parser | Started |

See [`docs/PROGRESS.md`](docs/PROGRESS.md) for the dated log.

## Running the NS2 part

Needs Ubuntu or WSL.

```bash
sudo apt install ns2 nam
cd ns2
ns netmind_scenario.tcl          # creates netmind.tr and netmind.nam
nam netmind.nam                  # watch the simulation
python3 parse_trace.py netmind.tr   # metrics per second -> netmind_metrics.csv
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Packet capture needs administrator rights (and Npcap on Windows). Only capture traffic on networks you own or have permission to monitor.
