"""Builds NetMind_Code_Reference.pdf: the formulas, constants, data structures, tools and every
function and class in the project, each with a one-line comment.

Function names are read from the source with `ast`, so the list always matches the code. Comments
come from each docstring's first sentence; functions without a docstring use COMMENTS below.
Run: python docs/review-2/build_reference.py
"""
from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import build_split_notes as B  # noqa: E402

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, KeepTogether  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402

MAROON, DEEP, MAROON_L = colors.HexColor("#560E1D"), colors.HexColor("#3A0812"), colors.HexColor("#F6E9EC")
SKY, SKY_D, SKY_L, SKY_C = (colors.HexColor(c) for c in ("#3E9BD6", "#1F6FA8", "#E1F0FA", "#8ED0F6"))
W, P, table, H = B.W, B.P, B.table, B.H

# ------------------------------------------------------------------ one-line comments
COMMENTS = {
    # command line
    "netmind/__main__.py:_db": "opens the SQLite database named by --db",
    "netmind/__main__.py:_print_report": "prints a run's summary, incidents and health to the terminal",
    "netmind/__main__.py:cmd_demo": "`demo`: generates the synthetic traffic, analyses it and prints the report",
    "netmind/__main__.py:cmd_capture": "`capture`: live capture with Scapy for N seconds, then analysis",
    "netmind/__main__.py:_load_model": "loads a saved anomaly model if --model was given",
    "netmind/__main__.py:cmd_pcap": "`pcap`: analyses a .pcap/.pcapng file",
    "netmind/__main__.py:cmd_ns2": "`ns2`: analyses an NS2 trace file as a new run",
    "netmind/__main__.py:cmd_runs": "`runs`: lists the stored runs",
    "netmind/__main__.py:cmd_report": "`report`: prints the report of a run (latest by default)",
    "netmind/__main__.py:cmd_hosts": "`hosts`: prints hosts, connection outcomes, DNS and health",
    "netmind/__main__.py:cmd_ask": "`ask`: asks the Copilot a question about a run",
    "netmind/__main__.py:cmd_routes": "`routes`: shortest path and Link State vs Distance Vector tables",
    "netmind/__main__.py:cmd_interfaces": "`interfaces`: lists capture interfaces",
    "netmind/__main__.py:cmd_api": "`api`: starts the FastAPI server (docs at /docs)",
    "netmind/__main__.py:cmd_dashboard": "`dashboard`: starts the Streamlit dashboard on port 8501",
    "netmind/__main__.py:main": "parses the command line and runs the chosen sub-command",
    # insights
    "netmind/analyzer/insights.py:_key": "builds a 'client:port>server:port' key to match packets of one connection",
    "netmind/analyzer/insights.py:grade": "turns a health score into Good (90+), Fair (70-90) or Poor",
    "netmind/analyzer/insights.py:health_summary": "the run's average health, its grade and the worst window",
    # detector
    "netmind/anomaly/detector.py:_clean": "keeps the feature columns as numbers and fills gaps",
    "netmind/anomaly/detector.py:AnomalyDetector.__init__": "sets up the 200-tree Isolation Forest and the z thresholds (6 and 4)",
    "netmind/anomaly/detector.py:AnomalyDetector._tf": "log(1 + x) of each feature so huge values don't dominate",
    "netmind/anomaly/detector.py:AnomalyDetector.fit": "learns normal: scales, trains the forest, sets the threshold, median and MAD",
    "netmind/anomaly/detector.py:AnomalyDetector.deviations": "robust z-score of every feature: (x - median) / spread",
    "netmind/anomaly/detector.py:AnomalyDetector.save": "saves the trained detector with joblib",
    "netmind/anomaly/detector.py:AnomalyDetector.load": "loads a saved detector",
    "netmind/anomaly/episodes.py:classify": "names an incident from its strongest features: scan, congestion, flood, spike",
    # api
    "netmind/api.py:db": "opens the database once and reuses it",
    "netmind/api.py:_check": "returns the run or a 404 error if it does not exist",
    "netmind/api.py:root": "GET /: API name and links",
    "netmind/api.py:health": "GET /health: status, version and number of runs",
    "netmind/api.py:runs": "GET /runs: every stored run",
    "netmind/api.py:run": "GET /runs/{id}: one run and its summary",
    "netmind/api.py:_table": "makes a GET endpoint for one stored table (metrics, flows, ...)",
    "netmind/api.py:_table.handler": "returns that table's rows for the run",
    "netmind/api.py:insights": "GET /runs/{id}/insights: health, connections and DNS",
    "netmind/api.py:incidents": "GET /runs/{id}/incidents: the incidents found",
    "netmind/api.py:topology": "GET /runs/{id}/topology: nodes and links",
    "netmind/api.py:_graph": "rebuilds the topology graph of a run",
    "netmind/api.py:path": "GET /runs/{id}/path: Dijkstra shortest path between two hosts",
    "netmind/api.py:routing": "GET /runs/{id}/routing: Link State and Distance Vector tables of a node",
    "netmind/api.py:Question": "the body of POST /ask: question, run id, backend",
    "netmind/api.py:ask": "POST /ask: the Copilot's answer about a run",
    # capture
    "netmind/capture/ns2.py:_node": "node number from an NS2 address like '3.0'",
    "netmind/capture/ns2.py:_events": "accepts a trace path or an already-read events table",
    "netmind/capture/ns2.py:_data": "keeps data packets (tcp, cbr...), drops routing and ack messages",
    "netmind/capture/sniffer.py:_flags": "TCP flags as text: S, SA, A, PA, FA, R",
    "netmind/capture/sniffer.py:packets_to_frame": "converts Scapy packets to the packet table",
    "netmind/capture/sniffer.py:list_interfaces": "names of the network interfaces Scapy can capture on",
    "netmind/capture/synthetic.py:_event_at": "which injected problem (if any) is active at time t",
    "netmind/capture/synthetic.py:_Gen": "the traffic generator: keeps the random seed, records and client ports",
    "netmind/capture/synthetic.py:_Gen.__init__": "seeds the random generator so every run is reproducible",
    "netmind/capture/synthetic.py:_Gen.loss": "drops a packet at random during congestion (7% by default)",
    "netmind/capture/synthetic.py:_Gen.tcp": "adds one TCP packet record",
    "netmind/capture/synthetic.py:_Gen.next_port": "next ephemeral client port (49152 upwards)",
    "netmind/capture/synthetic.py:_Gen.dns": "a DNS query and its response, same transaction id",
    "netmind/capture/synthetic.py:_Gen.web": "a full TCP connection: handshake, request, response, close",
    "netmind/capture/synthetic.py:_Gen.ping": "an ICMP echo request and (unless lost) its reply",
    # copilot
    "netmind/copilot/copilot.py:_fmt_feature": "'ports 311 vs normal 10' text for one feature",
    "netmind/copilot/copilot.py:incidents_to_text": "the incidents and their evidence as text for the prompt",
    "netmind/copilot/copilot.py:build_prompt": "question + network state + incidents + retrieved knowledge [1]-[4]",
    "netmind/copilot/copilot.py:_post": "sends a JSON request with the standard library (no extra package)",
    "netmind/copilot/copilot.py:call_anthropic": "asks the Claude API (needs ANTHROPIC_API_KEY)",
    "netmind/copilot/copilot.py:ollama_url": "where the local Ollama server is (localhost:11434)",
    "netmind/copilot/copilot.py:call_ollama": "asks a local Ollama model (llama3.2 by default)",
    "netmind/copilot/copilot.py:ollama_available": "checks whether Ollama is running",
    "netmind/copilot/copilot.py:pick_backend": "chooses Claude, Ollama or offline from what is available",
    "netmind/copilot/copilot.py:_topics": "which topics a question is about (scan, congestion, DNS...)",
    "netmind/copilot/copilot.py:_first_sentences": "the first n sentences of a text",
    "netmind/copilot/copilot.py:offline_answer": "rule-based answer from the incidents and notes, no LLM",
    "netmind/copilot/copilot.py:offline_answer.ref": "the [n] citation for a knowledge note",
    "netmind/copilot/copilot.py:Copilot": "the Copilot: knowledge base, backend and top-k (4)",
    "netmind/copilot/copilot.py:Copilot.__init__": "builds the TF-IDF knowledge base and picks the backend",
    "netmind/copilot/copilot.py:Copilot.retrieve": "finds the notes relevant to the question and the incidents",
    "netmind/copilot/copilot.py:Copilot.ask": "retrieve, build the prompt, answer; falls back to offline on failure",
    # dashboard
    "netmind/dashboard/app.py:_st_version": "installed Streamlit version, for compatibility",
    "netmind/dashboard/app.py:chart": "draws a Plotly chart full width",
    "netmind/dashboard/app.py:_db_path": "database path from --db, NETMIND_DB or data/netmind.db",
    "netmind/dashboard/app.py:get_db": "opens the database (cached)",
    "netmind/dashboard/app.py:get_copilot": "creates the Copilot once (cached)",
    "netmind/dashboard/app.py:esc": "escapes text before putting it in HTML",
    "netmind/dashboard/app.py:flash": "stores a success or error message for the next refresh",
    "netmind/dashboard/app.py:cb_ask": "queues a question for the Copilot",
    "netmind/dashboard/app.py:cb_ask_and_open": "queues a question and opens the Copilot page",
    "netmind/dashboard/app.py:cb_overview_submit": "sends the question typed in the Overview panel",
    "netmind/dashboard/app.py:_select_new_run": "selects a newly made run and opens Overview",
    "netmind/dashboard/app.py:cb_demo": "Generate and analyse: makes a synthetic demo run",
    "netmind/dashboard/app.py:cb_upload": "Analyse file: analyses an uploaded pcap or NS2 trace",
    "netmind/dashboard/app.py:cb_capture": "Capture and analyse: live capture from the sidebar",
    "netmind/dashboard/app.py:cb_ns2_analyse": "NS2 lab: turns the checked trace into a NetMind run",
    "netmind/dashboard/app.py:cb_delete": "deletes a run and its chat",
    "netmind/dashboard/app.py:answer_pending": "answers the queued question and saves it to the chat history",
    "netmind/dashboard/app.py:show_history": "shows the conversation with backend and sources",
    "netmind/dashboard/app.py:copilot_panel": "the Copilot box on the Overview page",
    "netmind/dashboard/app.py:page_overview": "Overview page: traffic trace, KPIs, latency/loss, protocols, Copilot",
    "netmind/dashboard/app.py:page_incidents": "Incidents page: score chart, one card per incident with evidence",
    "netmind/dashboard/app.py:page_traffic": "Traffic page: protocols and the searchable flow table",
    "netmind/dashboard/app.py:page_hosts": "Hosts & services page: scanner warning, hosts, connections, DNS",
    "netmind/dashboard/app.py:page_performance": "Performance page: health, latency, jitter, loss, throughput panels",
    "netmind/dashboard/app.py:page_topology": "Topology & routing page: graph, Dijkstra, LS vs DV, link failure",
    "netmind/dashboard/app.py:page_ns2": "NS2 lab page: topology, TCL script, how to run, checks, RED comparison",
    "netmind/dashboard/app.py:page_copilot": "Copilot page: chat, suggestions, model and the exact prompt",
    "netmind/dashboard/app.py:page_compare": "Compare runs page: two runs side by side",
    "netmind/dashboard/app.py:page_data": "Data & export page: downloads, raw tables, delete",
    "netmind/dashboard/charts.py:style": "common chart look: size, margins, font, transparent background",
    "netmind/dashboard/charts.py:_bands": "draws the red incident bands on a chart",
    "netmind/dashboard/charts.py:anomaly_chart": "anomaly score over time with the threshold line",
    "netmind/dashboard/charts.py:hbars": "horizontal bar chart (protocols, talkers, DNS names)",
    "netmind/dashboard/charts.py:zoom_chart": "one feature zoomed around an incident, normal level dashed",
    "netmind/dashboard/charts.py:rtt_boxes": "RTT distribution per type: handshake, ping, DNS (log scale)",
    "netmind/dashboard/charts.py:compare_chart": "one measure of two runs on the same axes",
    "netmind/dashboard/charts.py:topology_chart": "the host graph, shortest path highlighted, failed link marked",
    "netmind/dashboard/logic.py:_num": "a float, or None for missing values",
    "netmind/dashboard/logic.py:_fmt": "number with its unit, or 'n/a'",
    "netmind/dashboard/logic.py:kpis.col": "a metrics column as a list for the sparkline",
    "netmind/dashboard/logic.py:kpi_cards_html": "HTML for the row of KPI cards",
    "netmind/dashboard/logic.py:feature_name": "readable name of a feature ('dst_ports' -> 'Destination ports')",
    "netmind/dashboard/ns2lab.py:scenario_source": "the text of netmind_scenario.tcl",
    "netmind/pipeline.py:_save_common": "adds health, then saves metrics, scores, incidents and topology",
    # rag
    "netmind/rag/engine.py:Chunk": "one piece of a knowledge note: id, file, title, text",
    "netmind/rag/engine.py:TfidfEmbedder": "turns text into TF-IDF vectors (works offline)",
    "netmind/rag/engine.py:TfidfEmbedder.__init__": "TF-IDF with words and word pairs, English stop words removed",
    "netmind/rag/engine.py:TfidfEmbedder.fit": "learns the vocabulary from the chunks",
    "netmind/rag/engine.py:TfidfEmbedder.encode": "text -> TF-IDF vector",
    "netmind/rag/engine.py:SentenceEmbedder": "optional: Sentence-Transformers embeddings (all-MiniLM-L6-v2)",
    "netmind/rag/engine.py:SentenceEmbedder.__init__": "loads the embedding model",
    "netmind/rag/engine.py:SentenceEmbedder.fit": "nothing to learn: the model is pre-trained",
    "netmind/rag/engine.py:SentenceEmbedder.encode": "text -> normalised embedding vector",
    "netmind/rag/engine.py:SentenceEmbedder.__getstate__": "saves only the model name, not the weights",
    "netmind/rag/engine.py:SentenceEmbedder.__setstate__": "reloads the model by name",
    "netmind/rag/engine.py:_normalise": "scales vectors to length 1 so a dot product is cosine similarity",
    "netmind/rag/engine.py:VectorStore.__init__": "stores the vectors, in a FAISS index if FAISS is installed",
    "netmind/rag/engine.py:VectorStore.backend": "'faiss' or 'numpy'",
    "netmind/rag/engine.py:VectorStore.search": "the k chunks with the highest cosine similarity to the query",
    "netmind/rag/engine.py:VectorStore.__getstate__": "saves the vectors only",
    "netmind/rag/engine.py:VectorStore.__setstate__": "rebuilds the index from the vectors",
    "netmind/rag/engine.py:KnowledgeBase": "the knowledge base: chunks + embedder + vector store",
    "netmind/rag/engine.py:KnowledgeBase.__init__": "keeps the chunks, embedder and store together",
    "netmind/rag/engine.py:KnowledgeBase.build": "loads the 9 notes, chunks them and builds the index",
    "netmind/rag/engine.py:KnowledgeBase.search": "top-k chunks for a query, scores of at least 0.05",
    "netmind/rag/engine.py:KnowledgeBase.info": "number of chunks and documents, embedder and store used",
    "netmind/rag/engine.py:KnowledgeBase.save": "saves the built knowledge base",
    "netmind/rag/engine.py:KnowledgeBase.load": "loads a saved knowledge base",
    # storage
    "netmind/storage/db.py:NetMindDB": "the SQLite database of runs and their tables",
    "netmind/storage/db.py:NetMindDB.__init__": "opens (or creates) the database file and the runs table",
    "netmind/storage/db.py:NetMindDB.new_run": "adds a run row and returns its id",
    "netmind/storage/db.py:NetMindDB.update_summary": "replaces a run's JSON summary",
    "netmind/storage/db.py:NetMindDB.runs": "all runs, newest first",
    "netmind/storage/db.py:NetMindDB.run": "one run with its summary",
    "netmind/storage/db.py:NetMindDB.latest_run_id": "id of the newest run",
    "netmind/storage/db.py:NetMindDB.save": "writes a table (metrics, flows, ...) for a run",
    "netmind/storage/db.py:NetMindDB.load": "reads a table for a run",
    "netmind/storage/db.py:NetMindDB.delete_run": "deletes a run from every table",
    "netmind/storage/db.py:NetMindDB.close": "closes the database connection",
    # topology
    "netmind/topology/graph.py:_kind": "labels a host gateway, local, external or NS2 node",
    "netmind/topology/graph.py:edges_frame": "graph links as a table for storage",
    "netmind/topology/graph.py:nodes_frame": "graph nodes as a table for storage",
    # ns2 scripts
    "ns2/check_trace.py:node": "node number from an NS2 address",
    "ns2/check_trace.py:load": "reads the trace: packet events, link up/down lines, other lines",
    "ns2/check_trace.py:analyse": "follows every data packet: send, receive or drop time and its hops",
    "ns2/check_trace.py:main": "prints the per-flow, per-window, routes and scenario-check report",
    "ns2/check_trace.py:scenario_checks.window_stats": "drops and mean delay of packets sent in a time range",
    "ns2/compare_traces.py:phase_stats": "sent, drops, loss, delay and TCP goodput for one phase",
    "ns2/compare_traces.py:summarise": "phase table of one trace",
    "ns2/compare_traces.py:main": "prints two traces side by side and the burst summary line",
    "ns2/parse_trace.py:main": "full trace parser: per-window table, per-flow totals, CSV output",
}
# Docstrings whose first sentence is cut or too long for one line.
OVERRIDE = {
    "netmind/anomaly/detector.py:window_features": "the 10 features of every 2 s window (packets/s, ports, latency, ...)",
    "netmind/anomaly/detector.py:baseline": "the windows treated as normal: the first 60 s, or the first 30% (at least 8)",
    "netmind/anomaly/detector.py:detect": "trains on the baseline and scores every window; the whole detection step",
    "netmind/anomaly/episodes.py:episodes": "merges consecutive flagged windows into incidents with source, destination, protocol",
    "netmind/capture/ns2.py:packet_table": "one row per data packet: send, receive or drop time, delay, retransmission",
    "netmind/capture/ns2.py:_flow_jitter": "mean |change in delay| within each flow, averaged over flows",
    "netmind/capture/ns2.py:path_changes": "when each flow's route changed (finds the reroute via n4)",
    "netmind/capture/synthetic.py:_Gen.rtt": "random round-trip time; 4× larger and noisier during congestion",
    "netmind/copilot/copilot.py:insight_paragraphs": "answers about connections, DNS, hosts and health from the insight analysis",
    "netmind/dashboard/logic.py:simulate_link_failure": "routing table before and after removing a link, using Distance Vector",
    "netmind/dashboard/ns2lab.py:check": "the five checks, their numbers, drops per link and routes for one trace",
    "netmind/topology/graph.py:distance_vector_tables": "Distance Vector routing (Bellman-Ford rounds) and the rounds needed",
    "netmind/topology/graph.py:link_state_tables": "Link State routing: each node runs Dijkstra on the whole map",
    "netmind/dashboard/app.py:stretch": "makes a widget full width on old and new Streamlit",
}


def first_sentence(doc: str) -> str:
    text = " ".join(doc.split())
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    s = (m.group(1) if m else text).rstrip(".")
    return s[0].lower() + s[1:] if s and not s[:2].isupper() else s


def collect():
    files = sorted(list((REPO / "netmind").rglob("*.py")) + list((REPO / "ns2").glob("*.py")))
    out, missing = [], []
    for f in files:
        rel = f.relative_to(REPO).as_posix()
        tree = ast.parse(f.read_text())
        rows = []

        def visit(node, prefix=""):
            for ch in ast.iter_child_nodes(node):
                if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    q = f"{prefix}{ch.name}"
                    key = f"{rel}:{q}"
                    doc = ast.get_docstring(ch)
                    c = OVERRIDE.get(key) or COMMENTS.get(key) or (first_sentence(doc) if doc else None)
                    if c is None:
                        missing.append(key)
                        c = ""
                    kind = "class" if isinstance(ch, ast.ClassDef) else "def"
                    rows.append((ch.lineno, q, kind, c))
                    visit(ch, q + ".")

        visit(tree)
        if rows:
            out.append((rel, sorted(rows)))
    return out, missing


MODULE_ROLE = {
    "netmind/__main__.py": "command line: python -m netmind …",
    "netmind/api.py": "REST API (FastAPI)",
    "netmind/pipeline.py": "runs every module in order and saves the run",
    "netmind/capture/records.py": "M1: the packet-record format every input becomes",
    "netmind/capture/sniffer.py": "M1: Scapy live capture and pcap files",
    "netmind/capture/ns2.py": "M1: reading NS2 traces",
    "netmind/capture/synthetic.py": "M1: the synthetic demo with three injected problems",
    "netmind/analyzer/traffic.py": "M2: protocols, flows, top talkers",
    "netmind/analyzer/insights.py": "M2: connections, DNS, hosts, health score",
    "netmind/performance/metrics.py": "M4: latency, loss, jitter, throughput",
    "netmind/anomaly/detector.py": "M3: features, Isolation Forest, z-score",
    "netmind/anomaly/episodes.py": "M3: flagged windows → typed incidents",
    "netmind/topology/graph.py": "M5: graph, Dijkstra, Link State, Distance Vector",
    "netmind/storage/db.py": "M6: SQLite database",
    "netmind/rag/engine.py": "M7: knowledge base and retrieval",
    "netmind/copilot/copilot.py": "M8: prompt and answers",
    "netmind/dashboard/app.py": "M9: the Streamlit pages",
    "netmind/dashboard/charts.py": "M9: Plotly charts",
    "netmind/dashboard/logic.py": "M9: dashboard logic that can be tested without a browser",
    "netmind/dashboard/ns2lab.py": "M9: NS2 lab page logic",
    "ns2/check_trace.py": "NS2: the five scenario checks (standard library only)",
    "ns2/compare_traces.py": "NS2: DropTail vs RED by phase",
    "ns2/parse_trace.py": "NS2: full trace parser to CSV",
}


# ------------------------------------------------------------------ content
def fx(rows, head=MAROON):
    """Formula table: name, formula (mono), one-line comment."""
    data = [["Quantity", "Formula", "In one line"]]
    for n, f, c in rows:
        data.append([f"<b>{n}</b>", f"<font face='Mono' size='7.9'>{f}</font>", c])
    return table(data, [0.2, 0.42, 0.38], head=head)


def formulas():
    f = H(1, "Measurement formulas (M4)", MAROON)
    f.append(fx([
        ["TCP RTT", "t(SYN-ACK) − t(SYN), where ack = seq + 1", "handshake time; no probes sent"],
        ["Ping RTT", "t(echo reply, type 0) − t(echo request, type 8), same id + seq", "ICMP round trip"],
        ["DNS RTT", "t(response) − t(query), same transaction id", "lookup time"],
        ["Latency", "mean RTT per path (client, server, type), then averaged", "per path so 3 ms pings and 45 ms "
                                                                             "handshakes don't mix"],
        ["Jitter", "mean |RTTᵢ − RTTᵢ₋₁| on one path", "how much delay varies"],
        ["Loss %", "(retransmissions + unanswered pings) ÷ (TCP data segments + pings) × 100",
         "passive estimate: a resend means a loss"],
        ["Retransmission", "same direction, ports and seq seen twice with payload", "TCP resending lost data"],
        ["Throughput", "bytes × 8 ÷ window length (2 s) ÷ 10⁶", "Mb/s in each window"],
        ["Packets/s", "packets in window ÷ 2", "traffic rate"],
        ["Utilization %", "throughput ÷ link capacity × 100", "how full the link is"],
    ]))
    f += H(2, "Detection formulas (M3)", MAROON)
    f.append(fx([
        ["Features", "10 per 2 s window: pps, avg size, connections, conn duration, dst ports, TCP/UDP, "
                     "bytes/s, latency, loss, retx", "what the detector looks at"],
        ["TCP/UDP ratio", "TCP packets ÷ (UDP packets + 1)", "+1 avoids dividing by zero"],
        ["Transform", "log(1 + x), then standard scaling", "stops huge values dominating"],
        ["IF score", "s = 2^(−E[h(x)] / c(n))", "≈ 0.5 normal, near 1 unusual (few splits to isolate)"],
        ["c(n)", "2·H(n−1) − 2(n−1)/n, H = harmonic number", "average path length, normalises the score"],
        ["Threshold", "max(0.5, q99(baseline scores) + 0.03 + 0.25 ÷ √n)", "stricter when the baseline is short"],
        ["Robust z", "z = (x − median) ÷ (1.4826 × MAD)", "distance from normal in “units of spread”"],
        ["MAD", "median(|x − median|)", "spread that ignores odd values"],
        ["Spread floor", "max(MIN_SPREAD[f], 0.1 × |median|)", "a tiny wobble can't look huge"],
        ["Flag rule", "(score > threshold AND z ≥ 4) OR z ≥ 6", "both detectors, so congestion isn't missed"],
        ["Baseline", "first 60 s (demo) or first 30% of windows, at least 8 (16 s)", "what “normal” means"],
        ["Incident", "consecutive flagged windows merged", "one event, not many windows"],
        ["Severity", "peak z ≥ 30 High, ≥ 10 Medium, else Low", "colour of the incident card"],
    ]))
    f.append(P("<b>Incident type</b> (classify): dst_ports z ≥ 6, or connections z ≥ 10 with small packets → "
               "<b>port scan</b>; latency, loss or retx z ≥ 6 → <b>congestion</b>; pps z ≥ 6 with small packets → "
               "<b>flood</b>; performance z ≥ 3 → congestion; bytes/s or pps z ≥ 6 → <b>traffic spike</b>; "
               "else <b>unusual</b>.", "soft"))
    f += H(3, "Insight formulas (M2)", MAROON)
    f.append(fx([
        ["Connection state", "SYN → SYN-ACK = established; RST = refused; nothing = unanswered; "
                             "SYN-ACK then RST = reset", "outcome of each attempt"],
        ["Handshake time", "t(SYN-ACK) − t(SYN)", "median 45.7 ms in the demo"],
        ["Likely scanner", "failed attempts ≥ 20 AND distinct ports ≥ 20", "finds the scan without ML"],
        ["Latency penalty", "40 × clip((L ÷ L₀ − 1) ÷ 3, 0, 1)", "all 40 points lost at 4× normal"],
        ["Loss penalty", "40 × clip(loss ÷ 5, 0, 1)", "all 40 points lost at 5% loss"],
        ["Anomaly penalty", "20 if the window was flagged, else 0", ""],
        ["Health", "clip(100 − penalties, 0, 100), averaged over windows", "Good ≥ 90, Fair ≥ 70, else Poor"],
        ["Flow", "packets with the same 5-tuple, both directions merged", "one conversation"],
        ["Protocol share", "packets of protocol ÷ all packets × 100", ""],
    ]))
    f += H(4, "Routing (M5)", MAROON)
    f.append(fx([
        ["Link cost", "median measured RTT (ms), or 1 per hop", "the weight Dijkstra uses"],
        ["Dijkstra", "repeat: take the closest unfinished node, relax its links", "shortest path; costs must be ≥ 0"],
        ["Link State", "every node runs Dijkstra on the full map", "the OSPF idea"],
        ["Distance Vector", "Dᵤ(d) = minₙ [ c(u, n) + Dₙ(d) ], repeated until no change", "Bellman-Ford; the RIP idea"],
        ["DV rounds", "number of exchanges until nothing changes", "shown after a link failure"],
    ]))
    f += H(5, "RAG and Copilot (M7, M8)", MAROON)
    f.append(fx([
        ["TF-IDF", "tf(t, d) × log(N ÷ df(t)); sublinear tf, words + word pairs", "rare, relevant words weigh more"],
        ["Cosine similarity", "(q · d) ÷ (|q| × |d|)", "how close a note is to the question"],
        ["Chunks", "split at ## sections, at most 140 words", "small pieces to retrieve"],
        ["Retrieval", "top k = 4 chunks with score ≥ 0.05", "the [1]–[4] in the prompt"],
        ["Prompt", "QUESTION + NETWORK STATE + INCIDENTS + KNOWLEDGE", "the model sees data and theory"],
        ["Backend", "Claude if a key is set, else Ollama if running, else offline", "falls back to offline"],
    ]))
    f += H(6, "NS2 formulas", MAROON)
    f.append(fx([
        ["One-way delay", "t(r at destination) − t(+ at source)", "NS2 knows both times"],
        ["Loss %", "dropped ÷ (delivered + dropped) × 100", "drops are logged as d events"],
        ["Jitter", "mean |delayᵢ − delayᵢ₋₁| within a flow", ""],
        ["TCP goodput", "delivered TCP bytes × 8 ÷ phase length", "useful data rate (Mb/s)"],
        ["Bottleneck", "1 Mb/s, 20 ms, queue 10 packets (n2-n3)", "where congestion happens"],
        ["Backup cost", "3 per link (n2-n4, n4-n3)", "used only when n2-n3 is down"],
        ["RED", "drop prob. rises from 0 at avg queue 3 to max at 8 packets", "drops early so the queue stays short"],
        ["Phases", "normal 0.5–3, burst 3–6, recovery 6–7, link down 7–8.5, up 8.5–10 s",
         "compare_traces.py groups by these"],
    ]))
    return f


def constants():
    f = H(7, "Key constants and settings", MAROON)
    f.append(table([
        ["Constant", "Value", "Where", "In one line"],
        ["Window", "2 s (NS2: 0.5 s)", "pipeline.py", "every measure is computed per window"],
        ["NS2 baseline", "first 3 s", "analyze_ns2", "the period before the UDP burst"],
        ["n_estimators", "200", "AnomalyDetector", "trees in the Isolation Forest"],
        ["random_state", "42", "AnomalyDetector", "same model every run"],
        ["z_threshold / z_support", "6 / 4", "AnomalyDetector", "flag alone / flag with the forest"],
        ["MIN_TRAIN_WINDOWS", "8 (16 s)", "detector.py", "less traffic → “not enough to judge”"],
        ["train_fraction", "0.3", "baseline", "first 30% of windows is normal"],
        ["SCAN_MIN_FAILED / PORTS", "20 / 20", "insights.py", "likely-scanner rule"],
        ["LAT_MAX, LAT_FULL_RATIO", "40, 4×", "insights.py", "latency part of health"],
        ["LOSS_MAX, LOSS_FULL_PCT", "40, 5%", "insights.py", "loss part of health"],
        ["ANOM_MAX", "20", "insights.py", "anomaly part of health"],
        ["max_words / k / min_score", "140 / 4 / 0.05", "rag/engine.py", "chunk size, notes retrieved, cut-off"],
        ["Demo", "180 s, seed 7", "synthetic.py", "congestion 70–100, scan 120–128, flood 150–158 s"],
        ["Demo loss", "7% (pings 15%) in congestion", "synthetic.py", "packets dropped on purpose"],
        ["TCP window (NS2)", "6 packets", "netmind_scenario.tcl", "default 20 overflowed the queue alone"],
        ["UDP CBR (NS2)", "0.9 Mb/s, 3–6 s", "netmind_scenario.tcl", "the congestion burst"],
        ["Link failure (NS2)", "down 7.0 s, up 8.5 s", "rtmodel-at", "forces the DV reroute"],
        ["RED thresh_ / maxthresh_", "3 / 8", "netmind_scenario.tcl", "sized for the 10-packet queue"],
        ["Dashboard port", "8501", "Streamlit", "http://localhost:8501"],
    ], [0.26, 0.17, 0.21, 0.36], head=MAROON))
    f += H(8, "Data structures", MAROON)
    f.append(table([
        ["Structure", "Contents", "In one line"],
        ["Packet record (records.py)", "ts, src, dst, sport, dport, proto, app, length, payload_len, tcp_flags, seq, "
                                       "ack, icmp_type, icmp_id, icmp_seq, dns_id, dns_qr, dns_qname",
         "one row per packet, same for every input"],
        ["5-tuple / flow", "src IP, dst IP, src port, dst port, protocol", "identifies one conversation"],
        ["Run (SQLite runs table)", "id, name, source, created, summary (JSON)", "one analysis"],
        ["Run tables", "metrics, anomalies, incidents, flows, protocols, rtt, nodes, links, hosts, connections, dns",
         "all keyed by run_id"],
        ["Incident", "type, title, start_t, end_t, windows, peak_score, peak_deviation, top_features, top_src, "
                     "top_dst, top_proto", "one detected event and its evidence"],
        ["State (get_state)", "run, summary, overall, baseline, incidents, health, connections, dns, routes",
         "what the Copilot, API and dashboard read"],
        ["NS2 trace line", "event time from to type size flags fid src dst seq id", "+ − r d events"],
    ], [0.24, 0.48, 0.28], head=MAROON))
    f += H(9, "Tools and libraries", MAROON)
    f.append(table([
        ["Tool", "In one line"],
        ["Python 3", "the whole application"],
        ["Scapy + Npcap", "captures live packets and reads pcap files"],
        ["pandas / NumPy", "every table and calculation"],
        ["scikit-learn", "IsolationForest, StandardScaler and TfidfVectorizer"],
        ["NetworkX", "the topology graph and Dijkstra"],
        ["joblib", "saves trained models and the knowledge base"],
        ["SQLite (sqlite3)", "one-file database of runs; no server"],
        ["Streamlit + Plotly", "the web dashboard and its interactive charts"],
        ["FastAPI + Uvicorn", "the REST API with docs at /docs"],
        ["NS2 + TCL + NAM", "the network simulator, its script language and its animator"],
        ["Claude API / Ollama", "optional LLM backends for the Copilot"],
        ["Sentence-Transformers / FAISS", "optional embeddings and vector index"],
        ["pytest", "the automated tests"],
        ["argparse, urllib, json", "standard library: command line, HTTP calls, JSON"],
    ], [0.3, 0.7], head=MAROON))
    return f


def functions(mods):
    f = H(10, "Every function and class", MAROON)
    total = sum(len(r) for _, r in mods)
    f.append(P(f"All {total} functions and classes in netmind/ and ns2/, in file order, read from the source code. "
               "Methods are written <font face='Mono' size='8.3'>Class.method</font>; names starting with _ are "
               "internal helpers.", "soft"))
    cell = ParagraphStyle("fc", parent=B.S["cell"], fontSize=8, leading=10.6)
    for rel, rows in mods:
        head = Table([[Paragraph(f'<font color="white"><b>{rel}</b></font>&nbsp;&nbsp;'
                                 f'<font color="#{SKY_C.hexval()[2:]}">{MODULE_ROLE.get(rel, "")}</font>', cell)]],
                     colWidths=[W])
        head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), DEEP), ("LEFTPADDING", (0, 0), (-1, -1), 7),
                                  ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        data = [[Paragraph(f"<font face='Mono' size='7.6'>{'class ' if k == 'class' else ''}{q}</font>", cell),
                 Paragraph(c, cell)] for _, q, k, c in rows]
        t = Table(data, colWidths=[0.36 * W, 0.64 * W])
        st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, B.LINE),
              ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
              ("LEFTPADDING", (0, 0), (-1, -1), 6)]
        for i in range(0, len(data), 2):
            st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F3F8FC")))
        t.setStyle(TableStyle(st))
        f += [KeepTogether([head, t]) if len(rows) <= 14 else head, *([] if len(rows) <= 14 else [t]),
              Spacer(1, 6)]
    return f


def build(out: Path):
    mods, missing = collect()
    if missing:
        raise SystemExit("No comment for: " + ", ".join(missing))

    def first(cv, doc):
        cv.saveState()
        h = A4[1]
        cv.setFillColor(DEEP)
        cv.rect(0, h - 70 * mm, A4[0], 70 * mm, stroke=0, fill=1)
        cv.setFillColor(SKY_C)
        cv.setFont("Body-Semi", 10)
        cv.drawString(18 * mm, h - 22 * mm, "NETMIND, REVIEW 2")
        cv.setFillColor(colors.white)
        cv.setFont("Body-Bold", 30)
        cv.drawString(18 * mm, h - 40 * mm, "Code reference")
        cv.setFont("Body", 12)
        cv.setFillColor(colors.HexColor("#F0D5DB"))
        cv.drawString(18 * mm, h - 50 * mm, "Formulas, constants, tools and every function, one line each")
        cv.setFont("Body", 8.5)
        cv.setFillColor(colors.HexColor("#DDB0BA"))
        cv.drawString(18 * mm, h - 62 * mm, "Mohammed Affan (24BAI0014) and Hardik (24BCI0017)")
        cv.restoreState()
        later(cv, doc)

    def later(cv, doc):
        cv.saveState()
        cv.setFont("Body", 7.5)
        cv.setFillColor(B.MUTED)
        cv.drawString(18 * mm, 10 * mm, "NetMind, code reference")
        cv.setFillColor(MAROON)
        cv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"page {doc.page}")
        cv.setStrokeColor(B.LINE)
        cv.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
        cv.restoreState()

    story = [Spacer(1, 60 * mm),
             P("Sections 1–6 are the formulas, by module. Section 7 is the constants and settings, section 8 the "
               "data structures, section 9 the tools. Section 10 lists every function and class in the code with a "
               "one-line comment, generated from the source so nothing is missing.", "body")]
    story += formulas() + constants() + functions(mods)
    SimpleDocTemplate(str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                      bottomMargin=20 * mm, title="NetMind code reference",
                      author="Mohammed Affan, Hardik").build(story, onFirstPage=first, onLaterPages=later)
    return out


if __name__ == "__main__":
    print(build(Path(os.environ.get("NETMIND_NOTES_OUT", HERE)) / "NetMind_Code_Reference.pdf"))
