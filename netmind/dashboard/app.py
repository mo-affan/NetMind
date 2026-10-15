"""M9 NetMind Dashboard (Streamlit).

Run:  python -m netmind dashboard      (or: streamlit run netmind/dashboard/app.py)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root

from netmind.pipeline import analyze_ns2, analyze_packets, get_state  # noqa: E402
from netmind.storage import DEFAULT_DB, NetMindDB  # noqa: E402

# Colours: categorical slots 1-3 of the reference palette (validated colour-blind safe as a
# set), reserved status red for anomalies, quiet ink and gridlines.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
CRITICAL = "#d03b3b"
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SURFACE = "#fcfcfb"
KIND_COLOURS = {"local": BLUE, "gateway": ORANGE, "remote": AQUA, "ns2-node": BLUE}
KIND_NAMES = {"local": "Local host", "gateway": "Gateway", "remote": "Remote server",
              "ns2-node": "NS2 node"}

st.set_page_config(page_title="NetMind", page_icon="🛰️", layout="wide")

def _st_version() -> tuple[int, int]:
    try:
        major, minor = st.__version__.split(".")[:2]
        return int(major), int(minor)
    except (AttributeError, ValueError):
        return (0, 0)


# Streamlit 1.50 deprecated use_container_width (scheduled for removal) in favour of
# width="stretch"; older versions only understand use_container_width.
_NEW_WIDTH_API = _st_version() >= (1, 50)


def stretch(element, *args, **kwargs):
    """Full-width button / chart / table on both old and new Streamlit."""
    if _NEW_WIDTH_API:
        return element(*args, width="stretch", **kwargs)
    return element(*args, use_container_width=True, **kwargs)



def _args():
    # --db from `python -m netmind dashboard`, else NETMIND_DB, else data/netmind.db
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--db", default=os.environ.get("NETMIND_DB", str(DEFAULT_DB)))
    a, _ = p.parse_known_args()
    return a


@st.cache_resource
def get_db(path: str) -> NetMindDB:
    return NetMindDB(path)


@st.cache_resource
def get_copilot():
    from netmind.copilot import Copilot
    return Copilot()


def style(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor=SURFACE,
                      paper_bgcolor=SURFACE, font=dict(family="system-ui, Segoe UI, sans-serif",
                                                       color=INK2, size=12),
                      hoverlabel=dict(bgcolor="white", font_color=INK), showlegend=False)
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickcolor=AXIS, tickfont_color=MUTED)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=AXIS, tickfont_color=MUTED)
    return fig


def shade_incidents(fig, incidents, rows):
    for e in incidents:
        for r in rows:
            fig.add_vrect(x0=e["start_t"], x1=e["end_t"], fillcolor=CRITICAL, opacity=0.08,
                          line_width=0, row=r, col=1)
        fig.add_annotation(x=(e["start_t"] + e["end_t"]) / 2, y=1.0, yref="paper", text=e["title"],
                           showarrow=False, font=dict(size=11, color=CRITICAL), yanchor="bottom")


# ---------------------------------------------------------------------------
db = get_db(_args().db)

with st.sidebar:
    st.title("NetMind")
    st.caption("AI-Powered Network Intelligence and LLM Network Copilot")
    runs = db.runs()
    if runs.empty:
        st.info("No runs yet. Create one below.")
        run_id = None
    else:
        labels = {int(r.id): f"#{r.id} {r.name} ({r.source})" for r in runs.itertuples()}
        run_id = st.selectbox("Run", list(labels), format_func=labels.get)

    st.subheader("New run")
    if stretch(st.button, "Run synthetic demo",
                 help="Generated (not captured) traffic with congestion, a port scan and a ping flood"):
        from netmind.capture.records import to_frame
        from netmind.capture.synthetic import generate_scenario
        with st.spinner("Analysing synthetic demo traffic..."):
            analyze_packets(to_frame(generate_scenario()[0]), "Synthetic demo", "synthetic", db,
                            train_until=60)
        st.rerun()
    up = st.file_uploader("Upload a .pcap or NS2 .tr file", type=["pcap", "pcapng", "cap", "tr"])
    if up is not None and stretch(st.button, "Analyse upload"):
        suffix = Path(up.name).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(up.getvalue())
        try:
            with st.spinner(f"Analysing {up.name}..."):
                if suffix == ".tr":
                    analyze_ns2(f.name, up.name, db)
                else:
                    from netmind.capture.sniffer import read_pcap
                    analyze_packets(read_pcap(f.name), up.name, "pcap", db)
            st.rerun()
        except ImportError:
            st.error("Reading pcap files needs Scapy: `python -m pip install scapy`")
        except ValueError as e:
            st.error(f"Could not analyse {up.name}: {e}")
    st.caption("Live capture needs admin rights: `python -m netmind capture --duration 60`")

if run_id is None:
    st.header("Welcome to NetMind")
    st.write("Click **Run synthetic demo** in the sidebar to analyse generated traffic with "
             "three known problems, or upload a pcap / NS2 trace.")
    st.stop()

state = get_state(db, run_id)
metrics = db.load("metrics", run_id)
scores = db.load("anomalies", run_id)
incidents = state["incidents"]
o, base = state["overall"], state["baseline"]
is_ns2 = state["run"]["source"] == "ns2"
status = state.get("anomaly_status") or {}
if metrics.empty:
    st.warning("This run has no per-window metrics to show.")
    st.stop()
# columns that are empty for a whole run are not stored; add them back as blanks
for c in ("t", "pps", "latency_ms", "loss_pct", "throughput_mbps", "jitter_ms"):
    if c not in metrics.columns:
        metrics[c] = float("nan")
for c, default in (("anomaly_score", float("nan")), ("max_deviation", float("nan")),
                   ("is_anomaly", False)):
    if c not in scores.columns:
        scores[c] = default


def fmt(v, unit, digits=1):
    return "n/a" if v is None or pd.isna(v) else f"{v:.{digits}f} {unit}"

# ---- header and status -------------------------------------------------------
left, right = st.columns([3, 1])
left.header(f"{state['run']['name']}")
left.caption(f"Run #{run_id} · source: {state['run']['source']} · "
             f"{state['summary'].get('packets')} packets over {state['summary'].get('duration_s')} s")
if state["run"]["source"] in ("synthetic", "demo"):
    left.caption("Synthetic traffic generated by NetMind's demo, not a real capture.")
if status.get("state") == "insufficient_data":
    right.info("ℹ Anomaly detection skipped: not enough traffic")
elif incidents:
    right.error(f"⚠ {len(incidents)} incident{'s' if len(incidents) > 1 else ''} detected")
else:
    right.success("✓ No anomalies detected")

# ---- KPI tiles -----------------------------------------------------------------
peak = metrics.loc[metrics["latency_ms"].idxmax()] if metrics["latency_ms"].notna().any() else None
k = st.columns(5)
k[0].metric("Latency (normal)", fmt(base.get("latency_ms"), "ms"),
            help="Median latency per window in the normal baseline period")
if peak is not None:
    delta = (f"{peak['latency_ms'] - base['latency_ms']:+.1f} ms vs normal"
             if base.get("latency_ms") is not None else None)
    k[1].metric("Worst latency", fmt(peak["latency_ms"], "ms"), delta=delta,
                delta_color="inverse", help=f"at t={peak['t']:g} s")
else:
    k[1].metric("Worst latency", "n/a", help="No request/reply pairs to measure latency from")
k[2].metric("Throughput", fmt(o.get("throughput_mbps"), "Mbps", 3), help="Average over the run")
k[3].metric("Packet loss", fmt(o.get("loss_pct"), "%", 2),
            help="NS2: dropped / (delivered + dropped). Captures: (TCP retransmissions + "
                 "unanswered pings) / (data segments + pings)")
k[4].metric("Jitter", fmt(o.get("jitter_ms"), "ms"))

tab_overview, tab_copilot, tab_topology, tab_data = st.tabs(
    ["Traffic & anomalies", "Copilot", "Topology & routing", "Data"])

# ---- traffic and anomalies ---------------------------------------------------------
with tab_overview:
    rate_col, rate_name = ("pps", "Packets per second")
    rows = [(rate_col, rate_name), ("latency_ms", "Latency (ms)"),
            ("loss_pct", "Packet loss (%)")]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=[r[1] for r in rows] + ["Anomaly score"])
    for i, (col, name) in enumerate(rows, 1):
        fig.add_trace(go.Scatter(x=metrics["t"], y=metrics[col], mode="lines", name=name,
                                 line=dict(color=BLUE, width=2),
                                 hovertemplate=f"t=%{{x}} s<br>{name}: %{{y:.2f}}<extra></extra>"),
                      row=i, col=1)
    if not scores.empty and scores["anomaly_score"].notna().any():
        fig.add_trace(go.Scatter(x=scores["t"], y=scores["anomaly_score"], mode="lines",
                                 line=dict(color=BLUE, width=2), name="Anomaly score",
                                 hovertemplate="t=%{x} s<br>score %{y:.2f}<extra></extra>"),
                      row=4, col=1)
        a = scores[scores["is_anomaly"].astype(bool)]
        fig.add_trace(go.Scatter(x=a["t"], y=a["anomaly_score"], mode="markers", name="Anomalous window",
                                 marker=dict(color=CRITICAL, size=9, line=dict(color=SURFACE, width=2)),
                                 hovertemplate="t=%{x} s<br>anomalous, score %{y:.2f}<extra></extra>"),
                      row=4, col=1)
    shade_incidents(fig, incidents, [1, 2, 3, 4])
    fig.update_xaxes(title_text="time (s)", row=4, col=1)
    fig.update_annotations(font_size=12)
    stretch(st.plotly_chart, style(fig, 640))
    st.caption("Shaded bands are incidents. Red dots are windows the anomaly detector flagged.")

    st.subheader("Incidents")
    if status.get("state") == "insufficient_data":
        st.info(f"Anomaly detection was skipped: {status.get('reason')}.")
    elif not incidents:
        st.write("No anomalies: every window looks like the normal baseline.")
    for e in incidents:
        with st.container(border=True):
            st.markdown(f"**⚠ {e['title']}** · t = {e['start_t']:g}–{e['end_t']:g} s · "
                        f"peak score {e['peak_score']:.2f}")
            st.caption(f"Busiest: {e['top_proto']} from {e['top_src']} to {e['top_dst']}")
            stretch(st.dataframe, pd.DataFrame(e["top_features"]).rename(columns={
                "feature": "Feature", "value": "In incident", "normal": "Normal",
                "z": "Deviation"}), hide_index=True)
    for r in state["routes"]:
        st.caption(f"Route of flow {r['fid']} from t={r['t']:.2f} s: {r['path']}")

    protos = db.load("protocols", run_id)
    if not protos.empty:
        st.subheader("Protocol distribution")
        p = protos.sort_values("packets")
        pf = go.Figure(go.Bar(x=p["packets"], y=p["protocol"], orientation="h",
                              marker=dict(color=BLUE, cornerradius=4),
                              text=[f"{v:.1f}%" for v in p["share_pct"]], textposition="outside",
                              textfont=dict(color=INK2),
                              hovertemplate="%{y}: %{x} packets<extra></extra>"))
        pf.update_xaxes(title_text="packets")
        stretch(st.plotly_chart, style(pf, 60 + 40 * len(p)))

# ---- Copilot ---------------------------------------------------------------------
with tab_copilot:
    cp = get_copilot()
    st.caption(f"Answers use this run's measurements, its incidents and the networking knowledge "
               f"base. LLM backend: **{cp.backend}** "
               "(set ANTHROPIC_API_KEY for Claude, or run Ollama locally; otherwise offline mode). "
               "Advisory only: it never changes the network.")
    key = f"chat_{run_id}"
    st.session_state.setdefault(key, [])
    suggestions = ["What is causing the network slowdown?", "Is anyone attacking my network?",
                   "Did any link fail?", "What is jitter?"]
    cols = st.columns(len(suggestions))
    clicked = next((q for c, q in zip(cols, suggestions) if stretch(c.button, q)), None)
    for msg in st.session_state[key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    q = st.chat_input("Ask about your network...") or clicked
    if q:
        st.session_state[key].append({"role": "user", "content": q})
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                res = cp.ask(q, state)
            st.markdown(res["answer"])
            st.caption(f"backend: {res['backend']} · sources: " +
                       "; ".join(f"[{s['n']}] {s['title']}" for s in res["sources"]))
        st.session_state[key].append({"role": "assistant", "content": res["answer"]})

# ---- topology and routing ------------------------------------------------------------
with tab_topology:
    import networkx as nx
    from netmind.topology import (distance_vector_tables, graph_from_frames, link_state_tables,
                                  shortest_path)
    G = graph_from_frames(db.load("nodes", run_id), db.load("links", run_id))
    if G.number_of_nodes() == 0:
        st.write("No topology for this run.")
    else:
        weight = st.radio("Edge weight", ["latency", "hops"], horizontal=True,
                          help="latency = measured median RTT (ms); hops = every link costs 1")
        nodes = sorted(G.nodes)
        c1, c2 = st.columns(2)
        src = c1.selectbox("From", nodes, index=0)
        dst = c2.selectbox("To", nodes, index=len(nodes) - 1)
        try:
            sp = shortest_path(G, src, dst, weight)
            path_edges = set(zip(sp["path"], sp["path"][1:]))
        except nx.NetworkXNoPath:
            sp, path_edges = None, set()
        pos = nx.kamada_kawai_layout(G) if G.number_of_nodes() > 2 else nx.spring_layout(G, seed=1)
        tf = go.Figure()
        for a, b, d in G.edges(data=True):
            on = (a, b) in path_edges or (b, a) in path_edges
            tf.add_trace(go.Scatter(x=[pos[a][0], pos[b][0]], y=[pos[a][1], pos[b][1]], mode="lines",
                                    line=dict(color=INK if on else AXIS, width=3 if on else 1.5),
                                    hoverinfo="skip"))
        mx = [(pos[a][0] + pos[b][0]) / 2 for a, b in G.edges]
        my = [(pos[a][1] + pos[b][1]) / 2 for a, b in G.edges]
        tip = [f"{a} — {b}<br>{d.get('packets', 0)} packets<br>latency {d.get('latency', '?')} ms"
               + (f"<br>drops {d['drops']}" if 'drops' in d and d['drops'] == d['drops'] else "")
               for a, b, d in G.edges(data=True)]
        tf.add_trace(go.Scatter(x=mx, y=my, mode="markers", marker=dict(size=14, opacity=0),
                                hovertext=tip, hoverinfo="text"))
        kinds = sorted({G.nodes[n].get("kind", "local") for n in G.nodes})
        for kind in kinds:
            ns = [n for n in G.nodes if G.nodes[n].get("kind", "local") == kind]
            tf.add_trace(go.Scatter(
                x=[pos[n][0] for n in ns], y=[pos[n][1] for n in ns], mode="markers+text",
                name=KIND_NAMES.get(kind, kind), text=ns, textposition="top center",
                textfont=dict(color=INK2, size=11),
                marker=dict(size=18, color=KIND_COLOURS.get(kind, BLUE), line=dict(color=SURFACE, width=2)),
                hovertemplate="%{text}<extra>" + KIND_NAMES.get(kind, kind) + "</extra>"))
        style(tf, 460)
        tf.update_layout(showlegend=len(kinds) > 1, legend=dict(orientation="h", y=-0.05))
        tf.update_xaxes(visible=False)
        tf.update_yaxes(visible=False)
        stretch(st.plotly_chart, tf)
        if sp:
            st.markdown(f"**Dijkstra shortest path ({weight}):** {' → '.join(sp['path'])} "
                        f"· total cost {sp['cost']:g}")
        else:
            st.markdown("No path between these nodes.")
        ls = link_state_tables(G, weight)[src]
        dv, rounds = distance_vector_tables(G, weight)
        table = pd.DataFrame([{"Destination": d, "LS next hop": ls[d]["next_hop"], "LS cost": ls[d]["cost"],
                               "DV next hop": dv[src][d]["next_hop"], "DV cost": dv[src][d]["cost"]}
                              for d in sorted(ls)])
        st.subheader(f"Routing table of {src}")
        st.caption(f"Link State (Dijkstra on the full map) vs Distance Vector (Bellman-Ford, "
                   f"converged after {rounds} exchange rounds). Both reach the same costs.")
        stretch(st.dataframe, table, hide_index=True)

# ---- raw data ----------------------------------------------------------------------
with tab_data:
    st.subheader("Per-window metrics")
    stretch(st.dataframe, metrics, hide_index=True)
    st.subheader("Anomaly scores")
    stretch(st.dataframe, scores, hide_index=True)
    flows = db.load("flows", run_id)
    if not flows.empty:
        st.subheader("Top flows")
        stretch(st.dataframe, flows.head(100), hide_index=True)
    st.subheader("Normal baseline used by the detector")
    st.json(json.loads(json.dumps(base)))
