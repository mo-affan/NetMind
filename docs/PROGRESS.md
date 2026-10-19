# Progress log

Newest first.

| Date | Phase | What was done | Who |
| --- | --- | --- | --- |
| 2026-10-19 | Features | New analysis: TCP connection outcomes (established/refused/unanswered/reset, handshake time, likely scanners), DNS insights (lookups, unanswered, response time, top domains), host inventory (scope, role, services, traffic in/out), 0-100 network health score per window. Copilot answers questions about them; new dashboard page Hosts & services; health on every page header and the Performance page; `python -m netmind hosts`; API `/hosts`, `/connections`, `/dns`, `/insights`. NS2: optional RED queue on the bottleneck and `compare_traces.py` (RED run not executed yet; the default DropTail run uses the same commands as the executed version, but rerun it once to confirm) | Affan |
| 2026-10-15 | NS2 | **Executed** `netmind_scenario.tcl` in NS2 on Ubuntu 24.04: all 5 checks passed (delay 43.0 → 103.1 ms during the burst, 0 → 21 drops, rerouted via n4 at 115.2 ms) | Affan |
| 2026-10-15 | Dashboard | Redesigned the dashboard: new look (IBM Plex, teal theme), traffic-trace hero with incident bands, KPI cards with trends, Copilot panel on the Overview plus a full Copilot page, Incidents, Traffic explorer, Performance, link-failure simulator, run comparison, report/CSV export. Logic split into `dashboard/logic.py` with unit tests; AppTest tests for every page | Affan |
| 2026-10-15 | Repair | Diagnosed the "missing implementation" on the laptop (stale clone, see below). Hardened: empty/short captures, repo-anchored paths, optional-package errors, `/health`, synthetic labelling, Streamlit width API; fewer false alarms (stricter forest threshold, 16 s minimum baseline); split requirements; Windows setup/run scripts; CLI, edge-case, API and dashboard tests; README, Review 2 guide and demo script | Affan |
| 2026-10-15 | NS2 | Reviewed and fixed the NS2 scenario and trace parser; consistent metric definitions; standard-library lab checker; lab execution guide. Status: implemented, validated on a synthetic sample, **not yet executed in NS2** | Affan |
| 2026-10-13 | 1-8 | First full implementation: capture (Scapy live/pcap, NS2 traces, demo traffic), traffic analyzer, performance metrics, topology with Dijkstra/LS/DV, SQLite storage, Isolation Forest anomaly detection with incidents, RAG knowledge base, Copilot (Claude/Ollama/offline), pipeline, CLI, REST API, Streamlit dashboard, Docker, 32 tests | Affan |
| 2026-10-13 | Setup | Repository created with module folders, NS2 scenario and trace parser, Review 1 documents | Affan |
| 2026-10-08 | Review 1 | Presented proposal (9 slides). Faculty suggested adding NS2; added NS2 Simulation Module | Both |
| 2026-10-07 | Proposal | Review 1 proposal document submitted | Both |

## Current status (2026-10-15)

### Why the laptop checkout looked empty

The laptop clone (`C:\Users\moham\NetMind`) was made at 12:26 IST on 2026-10-13, after the first commit (`b1f6d55`, 12:19 IST) and before the implementation was pushed (`6b43ee7`, 12:49 IST). It was never fetched again, so it still had only the skeleton: `tests/.gitkeep`, `netmind/__init__.py` and `ns2/parse_trace.py`. `git status` said "up to date with origin/main" because that compares against the last *fetched* state, not GitHub. Fix: `git fetch origin` then `git merge --ff-only origin/main` (plus the repair commit below).

### Verification

Environment where checks were run: Linux sandbox, Python 3.13.16, numpy 2.5.3, pandas 3.0.5, scikit-learn 1.9.1, networkx 3.6.1, joblib 1.6.0. PyPI was blocked there, so pytest, FastAPI, Streamlit and Scapy could not be installed, and the test suite was run with a small stand-in runner that executes the same test functions and fixtures.

| Check | Result |
| --- | --- |
| Test functions (63) | **57 passed, 0 failed, 6 skipped** (skipped: pcap round-trip needs Scapy; API and health need FastAPI; 3 dashboard tests need Streamlit) |
| `python -m netmind --help`, `--version` | Passed |
| `python -m netmind demo` on a clean database, and rerun | Passed: 13,511 synthetic packets, 3 incidents (congestion 70-100 s, port scan 120-128 s, flood 150-158 s), about 3.6 s; rerun adds run 2 with identical results |
| `report`, `runs`, `ask` (offline), `routes` | Passed |
| `ns2 tests/data/sample_ns2.tr`, `ns2/check_trace.py`, `ns2/parse_trace.py` | Passed: congestion 3-6 s and reroute via n4 at 7 s; 5/5 scenario checks |
| Running from another folder; output through a cp1252 (Windows-style) console | Passed |
| Empty / 1-packet / 3 s / 8 s captures | Passed: empty rejected with a clear error; short ones report "not enough traffic" instead of "no anomalies" |
| False alarms, normal-only synthetic traffic, 20-180 s x 10 seeds | 3 flagged windows of about 1,350 (was 18 before this repair); detection of all injected events unchanged |
| Real pytest | **Not run** (blocked: pytest not installable in the sandbox) |
| Dashboard start (`python -m netmind dashboard`), dashboard AppTest | **Not run** (blocked: Streamlit not installable) |
| API (`python -m netmind api`, TestClient tests) | **Not run** (blocked: FastAPI not installable) |
| Pcap reading / live capture | **Not run** (blocked: Scapy not installable; live capture also needs admin rights) |
| Python 3.14, Windows, PowerShell scripts | **Not run** (no Windows/PowerShell in the sandbox, and the laptop was not reachable). Scripts were reviewed by hand for Windows PowerShell 5.1 pitfalls |
| NS2 TCL scenario | **Not executed** (no NS2; to be run in the college lab) |

On the laptop, `scripts\setup_windows.ps1` runs the real pytest suite, including the tests skipped here. Record its result in this table.

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
| Executed (scenario run in NS2) | **Done 2026-10-15** on Ubuntu 24.04 (team laptop); all 5 checks passed. RED variant: not run yet |

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

### Results from the real NS2 run (2026-10-15, Ubuntu 24.04 on the team laptop)

| Check (`check_trace.py`) | Result |
| --- | --- |
| No drops before the UDP burst (0.5-3 s) | PASS: 0 drops |
| Drops during the UDP burst (3-6 s) | PASS: 21 drops |
| Delay higher during the burst | PASS: 43.0 ms → 103.1 ms |
| Traffic rerouted via n4 during the link failure (7-8.5 s) | PASS |
| TCP delay higher on the backup path | PASS: 115.2 ms |

Still to record: the NS2 version and the trace file itself in `ns2/results/`. NAM did not open on that machine (it could not find the Tk library `tk.tcl`); see the checklist's Appendix B.
