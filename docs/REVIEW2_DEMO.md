# NetMind: Review 2 demo (3-5 minutes)

## Before the review (once, the day before)

```powershell
cd C:\Users\moham\NetMind
git fetch origin; git merge --ff-only origin/main     # latest code
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

`setup_windows.ps1` must end with "Setup complete" and the tests passing.

## 10 minutes before

1. Open **two** PowerShell windows in `C:\Users\moham\NetMind`, and run `.\.venv\Scripts\Activate.ps1` in both.
2. Start a clean demo database, so the run list is short (this keeps your normal database):
   ```powershell
   $env:NETMIND_DB = "$PWD\data\review2.db"
   ```
   Do this in **both** windows.
3. Window 2: `python -m netmind dashboard`. Leave it running; the browser opens at http://localhost:8501.
4. Close other apps; set the screen zoom so the terminal text is readable.

## The demo

| Time | Do | Say |
| --- | --- | --- |
| 0:00 | Window 1: `python -m netmind demo` | "This is synthetic traffic NetMind generates: three hosts browsing, DNS and pings, with three problems injected at known times: congestion at 70 s, a port scan at 120 s, a ping flood at 150 s. Labelled synthetic, so we know the truth." |
| 0:30 | Point at the per-window table | "Every 2 seconds NetMind measures packets per second, throughput, latency from TCP handshakes, pings and DNS, jitter per path, and loss from TCP retransmissions and unanswered pings." |
| 1:00 | Point at the three incidents | "The anomaly detector learned normal traffic from the first 60 seconds, then flagged three incidents, each with its evidence: latency 146 vs 27 ms and 9.5% loss, 311 destination ports vs 10 from 192.168.1.66, 551 packets per second of small ICMP packets." |
| 1:30 | Browser: refresh, select "Synthetic demo" | "The dashboard shows the same run: the shaded bands are the incidents; the red dots are windows the model flagged." |
| 2:00 | Copilot tab: click "Is anyone attacking my network?" | "The Copilot combines the incidents with retrieved networking knowledge. It names the scan, the attacker and what to check, and it cites its sources. It only advises; it never changes the network." |
| 2:45 | Topology tab: From 192.168.1.10 To 8.8.8.8; then weight "hops" | "Hosts seen in the traffic form a graph. Dijkstra gives the shortest path; the table compares Link State and Distance Vector routing: same costs, and DV converged in a few rounds." |
| 3:30 | Window 1: `python -m netmind ns2 tests\data\sample_ns2.tr` | "This is NS2's trace format: a TCP flow, a UDP burst at 3 s and a link failure at 7 s with Distance Vector rerouting. NetMind finds the congestion and the reroute through n4. This trace is a synthetic sample; the real NS2 run will be done in the lab." |
| 4:15 | (if time) `python -m netmind ask "What is jitter?"` | Concept questions are answered from the knowledge base. |
| 4:30 | Stop | |

## If something goes wrong

| Problem | Do |
| --- | --- |
| Dashboard does not open | Show the terminal demo and `python -m netmind ask "..."`; it carries the same results |
| Browser shows an old run | Pick "Synthetic demo" in the sidebar run list, or click "Run synthetic demo" |
| `No module named netmind.__main__` | Wrong folder or outdated checkout: `cd C:\Users\moham\NetMind`, then `git merge --ff-only origin/main` |
| Port 8501 busy | `python -m netmind dashboard --port 8502` |
| Asked about real traffic | If Scapy and Npcap are installed: run PowerShell as Administrator, `python -m netmind capture --duration 60`, browse during the capture. Otherwise say it is implemented but needs admin rights and Npcap |

## Honest answers to have ready

- The demo traffic is generated (synthetic); real captures go through the same pipeline.
- The NS2 trace shown is a synthetic sample in NS2 format; the TCL scenario will be run in the college lab.
- Detection thresholds were tuned on synthetic traffic.
