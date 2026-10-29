"""Builds NetMind_Dashboard_and_NS2_Guide.pdf: every dashboard page, how to use it, and how the
NS2 output from Ubuntu is shown. Reuses the layout helpers of build_split_notes.py.
Run: python docs/review-2/build_dashboard_guide.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_split_notes as B  # noqa: E402  (registers the fonts)

from reportlab.graphics.shapes import Drawing, Rect, String  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate,  # noqa: E402
                                Spacer, Table, TableStyle)
from reportlab.lib.styles import ParagraphStyle  # noqa: E402

MAROON = colors.HexColor("#560E1D")
DEEP = colors.HexColor("#3A0812")
MAROON_L = colors.HexColor("#F6E9EC")
SKY = colors.HexColor("#3E9BD6")
SKY_D = colors.HexColor("#1F6FA8")
SKY_L = colors.HexColor("#E1F0FA")
SKY_C = colors.HexColor("#8ED0F6")
W, P, bullets, table, box, H, INK, SOFT, LINE = B.W, B.P, B.bullets, B.table, B.box, B.H, B.INK, B.SOFT, B.LINE


def short(text):
    return B.short(text, SKY_D, SKY_L)


def mono(t):
    return f"<font face='Mono' size='8.3'>{t}</font>"


def terminal(text, title="Ubuntu terminal"):
    bar = Table([[P(f'<font color="#F0D5DB" size="7.6">●  ●  ●&nbsp;&nbsp;&nbsp;{title}</font>', "small")]],
                colWidths=[W])
    bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), DEEP), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    body = Table([[Preformatted(text, ParagraphStyle("t", parent=B.S["code"], textColor=colors.HexColor("#F4EDEF"),
                                                     fontSize=7.6, leading=10.2))]], colWidths=[W])
    body.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#22070D")),
                              ("LEFTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 7),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return KeepTogether([bar, body, Spacer(1, 7)])


def wireframe(rows, height=104):
    """Sketch of a page layout. rows: list of rows, each a list of (label, weight, kind)."""
    d = Drawing(W, height)
    d.add(Rect(0, 0, W, height, rx=6, ry=6, fillColor=colors.white, strokeColor=LINE, strokeWidth=0.8))
    d.add(Rect(0, 0, 70, height, rx=6, ry=6, fillColor=MAROON_L, strokeColor=None))
    d.add(String(8, height - 14, "Sidebar", fontName="Body-Semi", fontSize=7.2, fillColor=MAROON))
    for i, t in enumerate(["Run", "Page list", "Start a", "new run"]):
        d.add(String(8, height - 28 - i * 10, t, fontName="Body", fontSize=6.6, fillColor=SOFT))
    x0, gap = 78, 5
    avail_h = height - 12
    rh = (avail_h - gap * (len(rows) - 1)) / len(rows)
    y = height - 6 - rh
    fills = {"head": (MAROON, colors.white), "chart": (SKY_L, SKY_D), "card": (colors.HexColor("#F3F8FC"), INK),
             "panel": (DEEP, colors.white), "table": (colors.HexColor("#F7F4F5"), SOFT)}
    for row in rows:
        tot = sum(wt for _, wt, _ in row)
        x = x0
        for label, wt, kind in row:
            w = (W - x0 - 6 - gap * (len(row) - 1)) * wt / tot
            bg, fg = fills[kind]
            d.add(Rect(x, y, w, rh, rx=3, ry=3, fillColor=bg, strokeColor=None))
            d.add(String(x + w / 2, y + rh / 2 - 2.5, label, fontName="Body-Medium", fontSize=6.8, fillColor=fg,
                         textAnchor="middle"))
            x += w + gap
        y -= rh + gap
    return KeepTogether([d, Spacer(1, 6)])


def page_block(num, name, sketch, what, how, point, owner):
    f = H(num, name, MAROON)
    f.append(P(f'<font color="#{SKY_D.hexval()[2:]}"><b>Shown in the demo by:</b></font> {owner}', "soft"))
    f.append(sketch)
    rows = [["What you see", "How to use it"]]
    rows.append([Paragraph("<br/>".join(f"• {w}" for w in what), B.S["cell"]),
                 Paragraph("<br/>".join(f"{i + 1}. {h}" for i, h in enumerate(how)), B.S["cell"])])
    f.append(table(rows, [0.5, 0.5], head=MAROON, zebra=False))
    f.append(Spacer(1, 5))
    f.append(box([P(f'<font name="Body-Semi" color="#{MAROON.hexval()[2:]}">Point out</font>&nbsp;&nbsp;{point}',
                    "body", spaceAfter=0)], bg=MAROON_L, bar=MAROON))
    f.append(Spacer(1, 6))
    return f


# ---------------------------------------------------------------- content
def intro():
    f = []
    f += H(1, "Before you start", MAROON)
    f.append(P("Start the dashboard from PowerShell, in the project folder:", "body"))
    f.append(B.code("cd C:\\Users\\moham\\NetMind\n.\\.venv\\Scripts\\Activate.ps1\n"
                    "python -m netmind dashboard          # opens http://localhost:8501"))
    f.append(P("Every page belongs to one <b>run</b>: one analysed capture, file or demo, stored in SQLite. "
               "The <b>sidebar</b> chooses the run and the page, and makes new runs:", "body"))
    f.append(table([
        ["Sidebar control", "What it does"],
        ["Run (drop-down)", "picks which stored run every page shows; the newest is first"],
        ["Page list", "the ten pages in this guide"],
        ["Start a new run → Synthetic demo", "toggle the three injected problems on or off, set the seed (default 7) "
                                            "and length (60–600 s, default 180), then <b>Generate and analyse</b>"],
        ["Start a new run → Analyse a file", "upload a .pcap/.pcapng (e.g. from Wireshark) or an NS2 .tr trace, then "
                                            "<b>Analyse file</b>"],
        ["Start a new run → Live capture", "captures for N seconds with Scapy (needs Npcap and an Administrator "
                                          "terminal), then analyses it"],
        ["Theme", "light or dark: ⋮ menu at the top right → Settings"],
    ], [0.34, 0.66], head=MAROON))
    f.append(Spacer(1, 6))
    f.append(P("Every page has the same <b>header</b>: the run name, a <i>synthetic</i> tag for demo runs, the "
               "packets, duration, hosts and flows, the <b>health badge</b> (e.g. 82.4 Fair) and the "
               "<b>verdict</b> (e.g. 3 incidents found).", "body"))
    f.append(short("pick a run in the sidebar, then read it page by page. Make a fresh demo run before the "
                   "review so the newest run is the one you show."))
    return f


def pages():
    f = []
    f += page_block(2, "Overview", wireframe([
        [("Header: run, health badge, verdict", 1, "head")],
        [("Packets/s across the run, red incident bands", 1, "chart")],
        [("KPI cards", 1, "card")],
        [("Latency and loss over time", 2.15, "chart"), ("Copilot panel", 1, "panel")],
        [("Protocols", 1, "card"), ("Top talkers", 1, "card"), ("", 1.08, "panel")]], 118),
        ["Traffic trace for the whole run; each red band is one incident",
         "KPI cards: normal and worst latency, packet loss, throughput, jitter and the share of normal windows",
         "Latency and loss panels with the normal baseline drawn in",
         "Protocol shares, top talkers and a one-line list of incidents",
         "Copilot panel on the right with three suggested questions"],
        ["Read the verdict and health badge first",
         "Hover the trace or a band for exact values",
         "Click a suggested question (e.g. “Is anyone attacking my network?”) or type one and press Ask",
         "Go to Incidents for the evidence behind each band"],
        "the three red bands at 70–100 s, 120–128 s and 150–158 s; health 82.4 (Fair).",
        "Hardik, 0:00–0:45; Affan uses its Copilot panel at 2:45.")
    f += page_block(3, "Incidents", wireframe([
        [("Header", 1, "head")], [("Anomaly score over time, with the threshold line", 1, "chart")],
        [("Incident card: title, severity, time, source → destination", 1, "card")],
        [("What stood out (evidence bars)", 1, "chart"), ("Around the incident (zoom)", 1, "chart")]]),
        ["Anomaly score per 2 s window with the threshold, flagged windows marked",
         "One card per incident: type, severity, time, windows, peak score, busiest traffic",
         "<b>What stood out</b>: the features furthest from normal (e.g. ports 311 vs 10)",
         "<b>Around the incident</b>: that feature zoomed in, with the normal level",
         "Route changes table for NS2 runs"],
        ["Read the rule under the score chart (z ≥ 6, or forest + z ≥ 4)",
         "Open each card and compare the evidence bar with normal",
         "Click <b>Ask the Copilot about this incident</b>: it opens the Copilot with the question filled in"],
        "port scan card: 311 distinct ports vs about 10, from 192.168.1.66.",
        "Affan, 2:15.")
    f += page_block(4, "Traffic", wireframe([
        [("Header", 1, "head")], [("Packets by protocol", 1, "chart"), ("Bytes by protocol", 1, "chart")],
        [("Search box", 2, "card"), ("Protocol filter", 1, "card")], [("Top 10 flows + flow table", 1, "table")]]),
        ["Packets and bytes per protocol (TCP, UDP, ICMP, DNS, HTTP, HTTPS…)",
         "Flows: one per 5-tuple, both directions merged, with packets, bytes, duration",
         "Bar chart of the 10 largest flows"],
        ["Type an address or port in the search (e.g. 192.168.1.66 or :443)",
         "Filter by protocol with the multi-select",
         "Sort the table by any column"],
        "search 192.168.1.66 to see the scanner's hundreds of tiny flows.",
        "not in the 5-minute demo; useful if asked “what is a flow?”.")
    f += page_block(5, "Hosts & services", wireframe([
        [("Header", 1, "head")], [("Insight cards: connections, refused, DNS", 1, "card")],
        [("Likely port scanner warning", 1, "panel")],
        [("Host table: role, services", 1.35, "table"), ("Bytes per host", 1, "chart")],
        [("Connection outcomes", 1, "chart"), ("Services + DNS", 1, "table")]], 118),
        ["Cards: connection attempts and outcomes, DNS lookups and response time",
         "Yellow warning naming a likely scanner (≥ 20 failed attempts to ≥ 20 ports)",
         "Host table: scope (private/public), role (client, server, likely scanner), services answered",
         "TCP connection outcomes: established, refused, unanswered, reset",
         "DNS: most-looked-up domains, unanswered lookups, median response time"],
        ["Read the warning first",
         "Find the scanner row in the host table",
         "Open <b>All connection attempts</b> to see each SYN and its outcome",
         "Click <b>Ask the Copilot about these connections</b>"],
        "“192.168.1.66 made 1,000 failed attempts to 1,000 ports”, found without the ML model; 9 hosts, "
        "364 DNS lookups, median 29.3 ms.",
        "Hardik, 0:45–1:30.")
    f += page_block(6, "Performance", wireframe([
        [("Header", 1, "head")], [("Health · latency · jitter · loss", 1, "chart")],
        [("Throughput · packets/s · retransmissions", 1, "chart")],
        [("RTT by measurement type (log scale)", 1, "chart")]]),
        ["Seven stacked panels over time: health, latency (one-way delay for NS2), jitter, loss, "
         "throughput, packets/s, TCP retransmissions, each with incident bands and the normal level",
         "Round-trip times split by type: ping, TCP handshake, DNS",
         "Per-flow totals for NS2 runs"],
        ["Open <b>How these are measured</b> for the formulas (they change for NS2 runs)",
         "Compare the panels inside a red band with outside it"],
        "latency 146 ms vs 26.5 normal and loss 9.5% during congestion; ping ≈ 3 ms vs handshake ≈ 45 ms "
        "is why jitter is per path.",
        "not in the demo; supports Affan's slide 5.")
    f += page_block(7, "Topology & routing", wireframe([
        [("Header", 1, "head")],
        [("Cost", 1, "card"), ("From", 1, "card"), ("To", 1, "card"), ("Simulate a link failure", 1.4, "card")],
        [("Host graph with the shortest path highlighted", 1, "chart")],
        [("Routing table: LS vs DV", 1, "table"), ("After the link failure", 1, "table")]]),
        ["Graph of hosts that talked; node size = bytes sent, line width = packets",
         "Dijkstra shortest path and its total cost",
         "Routing table of the chosen host: next hop and cost by Link State and by Distance Vector",
         "After a failure: which routes changed and how many DV rounds it took"],
        ["Choose <b>Cost</b>: latency (median RTT) or hops",
         "Pick <b>From</b> 192.168.1.10 and <b>To</b> 8.8.8.8",
         "Pick a link in <b>Simulate a link failure</b>; the path and tables update"],
        "LS and DV give the same costs; after the failure DV re-converges and the table shows the changed routes.",
        "Hardik, 1:30–2:15.")
    f += page_block(8, "NS2 lab", wireframe([
        [("Header", 1, "head")], [("NS2 topology (n0–n4)", 1.1, "chart"), ("Timeline 0.5 s → 10 s", 1, "table")],
        [("TCL script", 1, "card"), ("How to run", 1, "card"), ("Check a trace", 1, "panel"),
         ("DropTail vs RED", 1, "card")],
        [("Selected tab: checks, delay cards, routes, phases / comparison", 1, "table")]]),
        ["The 5-node scenario drawn from the TCL file, with the bottleneck and backup path",
         "Timeline of what happens at 0.5, 3, 6, 7, 8.5 and 10 s",
         "<b>TCL script</b>: the full script with line numbers and a download button",
         "<b>How to run</b>: the Ubuntu commands and the expected first line",
         "<b>Check a trace</b>: the 5 checks, delay and drop cards, routes, per-phase table",
         "<b>DropTail vs RED</b>: phase-by-phase comparison and bar chart"],
        ["Copy the traces to Windows (section 13)",
         "Check a trace → Upload → choose netmind.tr",
         "Optionally <b>Analyse netmind.tr as a NetMind run</b> to see it on every other page",
         "DropTail vs RED → Trace A netmind.tr, Trace B red.tr"],
        "5 of 5 checks passed; RED 71.3 ms vs DropTail 103.1 ms. The bundled sample is synthetic, so upload "
        "your real trace when showing results.",
        "Affan's backup if Ubuntu misbehaves (3:15–5:00).")
    f += page_block(9, "Copilot", wireframe([
        [("Header", 1, "head")],
        [("Conversation with sources", 2.2, "panel"), ("Try asking + incident buttons + Model", 1, "card")],
        [("Ask about this run…", 2.2, "card"), ("", 1, "card")]]),
        ["Chat history for this run; each answer shows its backend and sources [1]–[4]",
         "Suggested questions and one “Explain: …” button per incident",
         "Model box: offline by default; Claude if ANTHROPIC_API_KEY is set; Ollama if installed",
         "<b>What the Copilot was given</b>: the exact prompt for the last question"],
        ["Type a question at the bottom, or click a suggestion",
         "Open the prompt expander to show it uses measured data and retrieved notes",
         "<b>Clear conversation</b> to start again"],
        "the answer names the port scan, the time and the evidence, and cites a note; numbers come from "
        "the database, and the Copilot only advises.",
        "Affan, 2:45 (from the Overview panel).")
    f += page_block(10, "Compare runs", wireframe([
        [("Header", 1, "head")], [("Run A", 1, "card"), ("Run B", 1, "card")],
        [("Side-by-side table", 1, "table")],
        [("Latency A vs B", 1, "chart"), ("Packets/s A vs B", 1, "chart")]]),
        ["Two runs side by side: packets, duration, hosts, flows, latency, loss, jitter, throughput, incidents",
         "Latency and packets/s of both runs on one chart"],
        ["Make a second run (e.g. demo with the problems toggled off, or another seed)",
         "Choose Run A and Run B"],
        "normal-only traffic (problems toggled off) against the demo: its latency and loss stay flat and the incident count drops to few or none.",
        "optional; good answer to “how do you know it isn't always flagging?”.")
    f += page_block(11, "Data & export", wireframe([
        [("Header", 1, "head")],
        [("Report (MD)", 1, "card"), ("Metrics CSV", 1, "card"), ("Scores CSV", 1, "card"),
         ("Incidents CSV", 1, "card")],
        [("Raw tables (expanders) + normal baseline", 1, "table")], [("Delete this run", 1, "panel")]]),
        ["Downloads: Markdown report, per-window metrics, anomaly scores, incidents",
         "Raw tables: metrics, scores, flows, hosts, TCP connections",
         "The normal baseline the detector learned",
         "Delete run, behind a confirmation tick box"],
        ["Download the report for the documentation",
         "Open the baseline to answer “what is normal?”"],
        "everything on screen is reproducible from these tables.",
        "not in the demo.")
    return f


# NS2 output, using the real run's recorded numbers
NS_OUT = """$ cd ~/netmind_ns2
$ ns netmind_scenario.tcl
NetMind NS2 scenario: running 10 s simulation, output base name 'netmind', bottleneck queue DropTail
t= 0.50 s  TCP flow n0 -> n3 starts
t= 3.00 s  UDP burst n1 -> n3 starts (congestion expected)
t= 6.00 s  UDP burst stops
t= 7.00 s  link n2-n3 down (DV should reroute via n4)
t= 8.50 s  link n2-n3 up
Simulation finished at t=10 s
Trace file:     netmind.tr
NAM animation:  netmind.nam   (open with: nam netmind.nam)"""

CHECK_OUT = """$ python3 check_trace.py netmind.tr
Trace: netmind.tr  (… packet events, last event at t=…)
Event counts: + tcp …, r tcp …, d cbr …, r rtProtoDV …

Per flow            fid, type, path, sent, delivered, dropped, loss %, avg delay
Per 1 s window      sent, drops, loss %, delay, throughput for t = 0 … 9 s
Dropped data packets per link: {'n2-n3': …}

Routes (new line = route changed):
  t=  0.500 s  flow 1: n0-n2-n3
  t=  7.0  s  flow 1: n0-n2-n4-n3        <- Distance Vector reroute
  t=  8.5  s  flow 1: n0-n2-n3           <- back on the main link

Scenario checks
  [PASS] no drops before the UDP burst (0.5-3 s)
  [PASS] drops during the UDP burst (3-6 s)
  [PASS] delay higher during the burst than before
  [PASS] traffic rerouted via n4 during the link failure (7-8.5 s)
  [PASS] TCP delay higher on the backup path
  (delay before burst 43.0 ms, during burst 103.1 ms, TCP during failure 115.2 ms;
   drops before 0, during 21)"""

CMP_OUT = """$ ns netmind_scenario.tcl red RED
NetMind NS2 scenario: running 10 s simulation, output base name 'red', bottleneck queue RED
...
$ python3 compare_traces.py netmind.tr red.tr
phase          sent  drop  loss%  delay ms  TCP Mb/s TCP drops
normal     A / B          same in both
UDP burst  A                     ...      103.1      ...
           B                     ...       71.3      ...
recovery, link down, link up     same in both

During the UDP burst: delay 103.1 ms (netmind) vs 71.3 ms (red); TCP goodput 0.153 vs 0.150 Mb/s."""


def ns2_section():
    f = [PageBreak(), B.PartBanner("Part 2", "How the NS2 output from Ubuntu is shown",
                                   "What each command prints, what it means, and where it appears in the dashboard.",
                                   MAROON), Spacer(1, 8)]
    f += H(12, "The three files", MAROON)
    f.append(table([
        ["File", "Made by", "What it is"],
        ["netmind_scenario.tcl", "you (the input)", "the network and the events: 5 nodes, links, TCP and UDP traffic, "
                                                   "the link failure; NS2 reads it"],
        ["netmind.tr", "NS2 (output)", "the trace: one line per packet event (+ enqueue, − dequeue, r receive, d drop) "
                                       "with time, nodes, type, size, flow, sequence number"],
        ["netmind.nam", "NS2 (output)", "the animation for NAM (optional)"],
    ], [0.24, 0.18, 0.58], head=MAROON))
    f.append(Spacer(1, 4))
    f.append(B.code("+ 0.5 0 2 tcp 1040 ------- 1 0.0 3.0 0 0\n"
                    "event  time  from  to  type  size  flags  flow  source  destination  seq  id"))
    f.append(short("TCL script in → NS2 runs it → trace file out → NetMind reads the trace."))

    f += H(13, "Step 1: run the simulation", MAROON)
    f.append(terminal(NS_OUT))
    f.append(P("Each <font face='Mono' size='8.3'>t=</font> line is printed by the script when that event fires, "
               "so it proves the scenario ran with the planned timeline. No numbers are measured yet.", "body"))
    f.append(P("<b>In the dashboard:</b> NS2 lab → <b>Timeline</b> table (same events) and the <b>How to run</b> tab, "
               "which shows this expected first line.", "body"))
    f.append(P("To use the traces on Windows, copy them out of Ubuntu:", "body"))
    f.append(B.code("cp ~/netmind_ns2/netmind.tr ~/netmind_ns2/red.tr /mnt/c/Users/moham/Downloads/"))

    f += H(14, "Step 2: check the trace", MAROON)
    f.append(P("The layout below is what check_trace.py prints. The summary line holds the numbers from your "
               "real run on 15 and 28 October; “…” marks values to read off your own screen.", "soft"))
    f.append(terminal(CHECK_OUT))
    f.append(table([
        ["Terminal section", "What it tells you", "Where it is in NS2 lab → Check a trace"],
        ["Trace / Event counts", "how many enqueue, receive and drop events of each type", "caption under Per phase"],
        ["Per flow", "TCP flow 1 and UDP flow 2: sent, delivered, dropped, delay", "Analyse as a NetMind run → "
                                                                              "Performance → Per-flow totals"],
        ["Per 1 s window", "delay and drops rise from 3 s, recover after 6 s", "Per phase table (grouped by phase)"],
        ["Dropped per link", "all drops on n2-n3, the bottleneck", "caption: Drops per link"],
        ["Routes", "flow 1 moves to n0-n2-n4-n3 at 7 s, back at 8.5 s", "Routes table"],
        ["Scenario checks", "the five PASS lines", "“5 of 5 checks passed” badge and green PASS rows"],
        ["Summary line", "43.0 → 103.1 ms, 0 → 21 drops, 115.2 ms via n4", "the four delay and drop cards"],
    ], [0.22, 0.4, 0.38], head=MAROON))
    f.append(short("the dashboard runs the same check code as check_trace.py, so the terminal and the NS2 lab "
                   "page always agree."))

    f += H(15, "Step 3: DropTail vs RED", MAROON)
    f.append(terminal(CMP_OUT))
    f.append(P("<b>In the dashboard:</b> NS2 lab → <b>DropTail vs RED</b>: Trace A = netmind.tr, Trace B = red.tr. "
               "It prints the same sentence (“During the UDP burst, mean delay is 103.1 ms with A and 71.3 ms with "
               "B…”), a bar chart of delay per phase and the full table.", "body"))
    f.append(P("Why RED is lower: it drops early, at random, once the average queue passes 3 packets, so the "
               "queue never fills; DropTail drops only when all 10 places are full.", "soft"))

    f += H(16, "Step 4 (optional): the NAM animation", MAROON)
    f += bullets(["<font face='Mono' size='8.3'>nam netmind.nam</font> opens the animation: packets move along the "
                  "links, queued packets stack at n2, dropped ones fall off, and at 7 s the n2-n3 link turns red "
                  "and traffic goes through n4.",
                  "If NAM won't open (a missing Tk library on WSL), skip it: the checks and the NS2 lab page show "
                  "the same events."], colour=MAROON)

    f += H(17, "One trace, every page", MAROON)
    f.append(P("Check a trace → <b>Analyse netmind.tr as a NetMind run</b> (or sidebar → Analyse a file) turns the "
               "trace into a normal run. Then:", "body"))
    f.append(table([
        ["Page", "What the NS2 run shows"],
        ["Overview", "packets/s and one-way delay over 10 s, incident bands around the burst and the failure"],
        ["Incidents", "congestion at 3–6 s; a reroute at 7–8.5 s; the Route changes (NS2) table"],
        ["Performance", "delay (receive − send), loss = dropped ÷ (delivered + dropped), per-flow totals"],
        ["Topology & routing", "n0–n4 as a graph; fail n2–n3 and DV picks n4"],
        ["Hosts & services", "empty connection view: NS2 traces carry no TCP flags, so this page is for captures"],
    ], [0.24, 0.76], head=MAROON))
    return f


def build(out: Path):
    def first(cv, doc):
        cv.saveState()
        h = A4[1]
        cv.setFillColor(DEEP)
        cv.rect(0, h - 82 * mm, A4[0], 82 * mm, stroke=0, fill=1)
        cv.setFillColor(SKY_C)
        cv.setFont("Body-Semi", 10)
        cv.drawString(18 * mm, h - 22 * mm, "NETMIND, REVIEW 2")
        cv.setFillColor(colors.white)
        cv.setFont("Body-Bold", 30)
        cv.drawString(18 * mm, h - 40 * mm, "Dashboard and NS2 guide")
        cv.setFont("Body", 12)
        cv.setFillColor(colors.HexColor("#F0D5DB"))
        cv.drawString(18 * mm, h - 50 * mm, "Every page, how to use it, and how the Ubuntu output appears")
        n = 18
        wd = (A4[0] - 36 * mm - 5 * (n - 1)) / n
        for i in range(n):
            cv.setFillColor(SKY_C if i == 0 else colors.Color(1, 1, 1, 0.18))
            cv.roundRect(18 * mm + i * (wd + 5), h - 66 * mm, wd, 3.2, 1.2, stroke=0, fill=1)
        cv.setFont("Body", 8.5)
        cv.setFillColor(colors.HexColor("#DDB0BA"))
        cv.drawString(18 * mm, h - 74 * mm, "Mohammed Affan (24BAI0014) and Hardik (24BCI0017)")
        cv.restoreState()
        later(cv, doc)

    def later(cv, doc):
        cv.saveState()
        cv.setFont("Body", 7.5)
        cv.setFillColor(B.MUTED)
        cv.drawString(18 * mm, 10 * mm, "NetMind, dashboard and NS2 guide")
        cv.setFillColor(MAROON)
        cv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"page {doc.page}")
        cv.setStrokeColor(LINE)
        cv.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
        cv.restoreState()

    story = [Spacer(1, 74 * mm),
             P("Part 1 walks through the ten dashboard pages in sidebar order: what each shows, how to use it and "
               "what to point out. Part 2 follows the NS2 run from the Ubuntu terminal to the NS2 lab page. Demo "
               "numbers are from the synthetic run (seed 7, 180 s); NS2 numbers are from the real run.", "body")]
    story += intro() + pages() + ns2_section()
    SimpleDocTemplate(str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                      bottomMargin=20 * mm, title="NetMind dashboard and NS2 guide",
                      author="Mohammed Affan, Hardik").build(story, onFirstPage=first, onLaterPages=later)
    return out


if __name__ == "__main__":
    print(build(Path(os.environ.get("NETMIND_NOTES_OUT", HERE)) / "NetMind_Dashboard_and_NS2_Guide.pdf"))
