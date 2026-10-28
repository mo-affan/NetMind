# NetMind

**AI-Powered Network Intelligence and LLM Network Copilot**

Computer Networks Lab (BCSE308P) project, VIT Vellore.

| Member | Reg. no. |
| --- | --- |
| Mohammed Affan | 24BAI0014 |
| Hardik | 24BCI0017 |

## What it does

Network monitoring tools show raw numbers (latency, packet loss, connections) but leave the interpretation to the user. NetMind:

1. **Measures.** Reads traffic, identifies protocols (TCP, UDP, ICMP, DNS, HTTP, HTTPS) and calculates latency, throughput, packet loss and jitter for every time window. It follows every TCP connection attempt (established, refused, unanswered, reset), matches DNS lookups to their answers, builds an inventory of hosts with their roles and services, and gives every window a 0-100 health score.
2. **Detects.** An Isolation Forest model plus a deviation-from-normal check flag unusual windows, which are grouped into incidents (congestion, port scan, flood, link failure).
3. **Explains.** A Copilot answers questions using the measured data and a networking knowledge base (RAG). It works offline by default; Claude or a local Ollama model can be plugged in. It only advises and never changes the network.

```
synthetic demo ─┐
pcap file ──────┤                                 ┌─ performance metrics ─┐
live capture ───┼─> packet records ─> traffic ────┼─ topology + routing ──┼─> SQLite ─┬─> dashboard (Streamlit)
NS2 trace ──────┘                     analysis    └─ anomaly detection ───┘           ├─> REST API (FastAPI)
                                                     └─> incidents                    └─> Copilot <── RAG knowledge base
```

## Status

| Part | Status |
| --- | --- |
| Synthetic demo, traffic analysis, metrics, anomaly detection, incidents, SQLite, RAG, offline Copilot, topology/routing, CLI | Working; covered by tests |
| NS2 scenario and trace analysis | Scenario **executed in NS2** on 2026-10-15 (Ubuntu 24.04), all 5 checks passed; analysis also tested on a synthetic sample trace. re-run 2026-10-28 with the same result. RED-queue variant executed 2026-10-28: 31% lower delay during congestion than DropTail (see `docs/PROGRESS.md`) |
| Dashboard, REST API, pcap reading | Implemented; their tests run only where Streamlit / FastAPI / Scapy are installed (see `docs/PROGRESS.md` for what was verified where) |
| Live capture | Implemented; needs Scapy, Npcap and an Administrator terminal; not covered by automated tests |
| Claude / Ollama Copilot backends | Implemented; optional; tests always use the offline backend |

## Requirements

- **Python 3.12, 3.13 or 3.14** (64-bit). 3.13 is the safest choice. All core packages publish wheels for 3.14; if `pip install` on 3.14 tries to *build* a package (errors mentioning "building wheel" or "Microsoft Visual C++"), use 3.13.
- Git.
- Nothing else for the demo: no internet after installation, no admin rights, no NS2, no API key.
- Optional: Scapy + [Npcap](https://npcap.com) for live capture / pcap files; NS2 (in the college lab) to *run* the simulation.

## Setup on Windows

### If your checkout is missing files

If `python -m netmind demo` says *"No module named netmind.__main__"* or `tests\` contains only `.gitkeep`, your clone is older than the implementation. Update it (safe: this refuses to run if it would overwrite anything):

```powershell
cd C:\Users\moham\NetMind
git status                      # should show no modified files
git fetch origin
git merge --ff-only origin/main
```

### Setup script (recommended)

From the repository folder, in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

It reuses `.venv` if it exists (otherwise creates it with Python 3.13, 3.12 or 3.14, in that order of preference), installs `requirements.txt` and `requirements-dev.txt`, tries the optional Scapy install, checks the imports and runs the tests. `-ExecutionPolicy Bypass` applies to that one command only; your settings are not changed. Options: `-PythonVersion 3.13`, `-Recreate` (renames the old `.venv` to `.venv.bak-<time>`, deletes nothing), `-SkipTests`, `-SkipCapture`.

### Manual setup

```powershell
py -3.13 -m venv .venv                       # or: py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1                 # if blocked: Set-ExecutionPolicy -Scope Process Bypass
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pip install -r requirements-capture.txt   # optional: Scapy
python -m pytest -q
```

Mac/Linux: `python3 -m venv .venv && source .venv/bin/activate`, then the same pip and pytest commands.

## Run

```powershell
python -m netmind demo                          # synthetic demo: congestion, port scan, ping flood
python -m netmind ask "Why is the network slow?"
python -m netmind dashboard                     # second terminal; opens http://localhost:8501
```

or `powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1 -Dashboard`.

### Dashboard pages

| Page | What it shows |
| --- | --- |
| Overview | The whole run as one traffic trace with incident bands, a verdict, six headline numbers with trend lines, latency and loss over time, protocols, top talkers, and the Copilot chat panel |
| Incidents | Anomaly score over time; per incident: severity, the features that stood out against normal, a zoomed chart and an "Ask the Copilot about this incident" button |
| Traffic | Packets and bytes by protocol; searchable, filterable flow table and the biggest flows |
| Hosts & services | Every host with its scope, role and the services it answered on; TCP connection outcomes per client and per service (a likely port scanner is called out); DNS lookups, response times and the most-queried domains |
| Performance | Health score, latency, jitter, loss, throughput, packets/s and retransmissions against their normal level; round-trip times by measurement type |
| Topology & routing | Host graph, Dijkstra path, Link State vs Distance Vector tables, and a link-failure simulator showing which routes change |
| NS2 lab | The NS2 scenario's topology (read from the TCL file) and timeline, the TCL script with a download button, the Ubuntu commands, the five scenario checks on an uploaded trace (same code as `ns2/check_trace.py`) with routes and per-phase numbers, and a DropTail vs RED comparison of two uploaded traces |
| Copilot | Full chat with suggested questions, per-incident questions, sources, and the exact prompt the model was given |
| Compare runs | Two runs side by side (for example the demo vs normal-only traffic) |
| Data & export | Markdown report and CSV downloads, raw tables, the detector's baseline, delete a run |

New runs (synthetic demo with a chosen seed and length, normal-only traffic, an uploaded pcap or NS2 trace, or a live capture) are started from **Start a new run** in the sidebar. Light and dark mode: the ⋮ menu at the top right, then **Settings** (needs Streamlit 1.51 or newer).

The demo's traffic is **generated, not captured**: 180 s of normal browsing, DNS and pings from three hosts, with congestion at 70-100 s, a port scan at 120-128 s and a ping flood at 150-158 s. It is deterministic (seed 7), takes a few seconds, and every run is stored as a new run in `data\netmind.db`.

### All commands

| Command | What it does |
| --- | --- |
| `python -m netmind demo [--duration S] [--seed N]` | Synthetic demo (also writes `data\demo.pcap` if Scapy is installed) |
| `python -m netmind pcap FILE` | Analyse a Wireshark/tcpdump capture (needs Scapy) |
| `python -m netmind capture --duration 60` | Live capture (Scapy, Npcap, Administrator terminal) |
| `python -m netmind interfaces` | List capture interfaces |
| `python -m netmind ns2 TRACE.tr` | Analyse an NS2 trace (no NS2 needed) |
| `python -m netmind runs` / `report [--run N]` | List runs / print a run's metrics and incidents |
| `python -m netmind hosts [--run N]` | Host inventory (scope, role, services), TCP connection outcomes, DNS and health score |
| `python -m netmind ask "QUESTION" [--run N] [--show-prompt]` | Ask the Copilot |
| `python -m netmind routes --from A --to B [--weight hops]` | Dijkstra path; Link State vs Distance Vector tables |
| `python -m netmind dashboard [--port 8501]` | Streamlit dashboard |
| `python -m netmind api [--port 8000]` | REST API; docs at http://127.0.0.1:8000/docs, health at `/health`; per run also `/hosts`, `/connections`, `/dns`, `/insights` |
| `python -m netmind --help` / `--version` | Help / version |

The database is `data\netmind.db` in the repository regardless of the folder you run from; set `NETMIND_DB` (or `--db`) to use another file.

### Copilot backends

| Backend | How to enable |
| --- | --- |
| Offline (default) | Nothing: rule-based answers from the same evidence and knowledge base |
| Claude (Anthropic API) | `$env:ANTHROPIC_API_KEY="..."`; model via `NETMIND_LLM_MODEL` (default `claude-haiku-5-5`) |
| Ollama (local, free) | Install [Ollama](https://ollama.com), `ollama pull llama3.2` |

`NETMIND_LLM=offline|anthropic|ollama` forces one. If an LLM call fails, the Copilot falls back to offline and says so.

## How the numbers are calculated

| Metric | Live/pcap/demo traffic | NS2 traces |
| --- | --- | --- |
| Latency | Request-to-reply time: TCP SYN to SYN-ACK (matched by sequence number), ICMP echo request to reply, DNS query to response; averaged per path | One-way delay: receive time - send time |
| Packet loss | (TCP retransmissions + unanswered pings) / (TCP data segments + pings); a passive capture cannot see lost packets directly | dropped / (delivered + dropped); in-flight packets excluded |
| Jitter | Mean absolute change between consecutive RTTs on the same path | Same, within each flow |
| Throughput | Bytes in the window x 8 / window length | Bytes delivered in the window |

**Health score.** Each window starts at 100 and loses up to 40 points for latency above normal (all 40 at 4x normal), up to 40 for loss (all 40 at 5%) and 20 if the anomaly detector flagged it; the run's score is the average (90+ Good, 70-90 Fair, below 70 Poor).

**TCP connections and DNS.** Each SYN is followed: established (SYN-ACK came back), refused (RST), unanswered (nothing) or reset (established, then RST). A host with 20+ failed attempts to 20+ different ports is marked as a likely scanner. DNS queries are matched to responses by transaction id.

**Anomaly detection.** 2-second windows (0.5 s for NS2) with 10 features: packets/s, average packet size, connections, connection duration, distinct destination ports, TCP/UDP ratio, bytes/s, latency, loss, retransmissions. The first part of the capture (default 30%, at least 16 s) is the normal baseline. A window is flagged when a feature is 6+ units of normal spread (robust z-score) from its normal value, or when the Isolation Forest score is above its threshold *and* some feature is 4+ units away. With less than 16 s of baseline, detection is skipped and reported as "not enough traffic" rather than "normal". On synthetic traffic (10 seeds) all injected events were detected and under 0.5% of normal windows were flagged.

## Tests

```powershell
python -m pytest -q
```

Tests need no network access, admin rights, NS2 or API key (the Copilot is forced offline). Tests for pcap reading, the API and the dashboard are skipped automatically if Scapy, FastAPI or Streamlit is not installed.

## NS2

NS2 is only needed to *run* the scenario, in the college lab. Analysing a trace needs only Python:

```powershell
python -m netmind ns2 path\to\netmind.tr      # full analysis
python ns2\check_trace.py path\to\netmind.tr  # quick check, standard library only
```

The scenario can also run with a RED queue on the bottleneck (`ns netmind_scenario.tcl red RED`); `ns2/compare_traces.py droptail.tr red.tr` compares the two phase by phase.

Lab instructions: [`docs/NS2_LAB_EXECUTION.md`](docs/NS2_LAB_EXECUTION.md). Scenario and definitions: [`ns2/README.md`](ns2/README.md).

## Repository layout

| Path | Module | Owner |
| --- | --- | --- |
| `netmind/capture/` | M1 input: Scapy live/pcap (`sniffer.py`), NS2 traces (`ns2.py`), synthetic traffic (`synthetic.py`), record format (`records.py`) | Hardik (NS2: Affan) |
| `netmind/analyzer/` | M2 protocols, flows (5-tuple), top talkers | Hardik |
| `netmind/anomaly/` | M3 window features, Isolation Forest + deviation check, incidents | Affan |
| `netmind/performance/` | M4 latency, throughput, loss, jitter, utilization | Affan |
| `netmind/topology/` | M5 graph, Dijkstra, Link State and Distance Vector | Hardik |
| `netmind/storage/` | M6 SQLite database | Hardik |
| `netmind/rag/` | M7 knowledge base (`knowledge/*.md`), chunking, TF-IDF or Sentence Transformers, vector search | Affan |
| `netmind/copilot/` | M8 Copilot (offline / Claude / Ollama) | Affan |
| `netmind/dashboard/` | M9 Streamlit dashboard | Hardik (lead) |
| `netmind/pipeline.py`, `api.py`, `__main__.py` | Pipeline, REST API, command line | Both |
| `ns2/` | NS2 scenario, trace parser, standard-library checker, `results/` for lab runs | Affan |
| `scripts/` | Windows setup and launch scripts | Both |
| `tests/` | pytest suite and synthetic NS2 sample trace | Both |
| `docs/` | Progress log, Review 1 documents, Review 2 guide and demo script, NS2 lab guide | Both |

## Docker

```bash
docker build -t netmind .
docker run -p 8501:8501 netmind      # dashboard at http://localhost:8501
```

## Ethics

Only capture traffic on networks you own or are permitted to monitor. The Copilot is advisory and never changes the network.
