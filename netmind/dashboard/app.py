"""M9 NetMind Dashboard (Streamlit).

Run:  python -m netmind dashboard      (or: streamlit run netmind/dashboard/app.py)

Pages: Overview (with the Copilot panel), Incidents, Traffic, Performance, Topology & routing,
Copilot, Compare runs, Data & export. The sidebar picks the run, the page, and starts new runs
(synthetic demo, uploaded pcap / NS2 trace, live capture).
"""
from __future__ import annotations

import argparse
import html
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root

from netmind.dashboard import charts, logic  # noqa: E402
from netmind.dashboard.theme import BRAND, CSS  # noqa: E402
from netmind.pipeline import analyze_ns2, analyze_packets, get_state  # noqa: E402
from netmind.storage import DEFAULT_DB, NetMindDB  # noqa: E402

PAGES = ["Overview", "Incidents", "Traffic", "Performance", "Topology & routing", "Copilot",
         "Compare runs", "Data & export"]
SUGGESTIONS = ["Why is the network slow?", "Is anyone attacking my network?",
               "Did any link fail?", "What is jitter?"]

st.set_page_config(page_title="NetMind", page_icon="🛰️", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _st_version() -> tuple[int, int]:
    try:
        major, minor = st.__version__.split(".")[:2]
        return int(major), int(minor)
    except (AttributeError, ValueError):
        return (0, 0)


# Streamlit 1.50 deprecated use_container_width in favour of width="stretch".
_NEW_WIDTH_API = _st_version() >= (1, 50)


def stretch(element, *args, **kwargs):
    """Full-width button / chart / table on both old and new Streamlit."""
    if _NEW_WIDTH_API:
        return element(*args, width="stretch", **kwargs)
    return element(*args, use_container_width=True, **kwargs)


def chart(fig, key=None):
    stretch(st.plotly_chart, fig, config={"displaylogo": False}, key=key)


def _db_path() -> str:
    # --db from `python -m netmind dashboard`, else NETMIND_DB, else data/netmind.db
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--db", default=os.environ.get("NETMIND_DB", str(DEFAULT_DB)))
    a, _ = p.parse_known_args()
    return a.db


@st.cache_resource
def get_db(path: str) -> NetMindDB:
    return NetMindDB(path)


@st.cache_resource
def get_copilot():
    from netmind.copilot import Copilot
    return Copilot()


def esc(x) -> str:
    return html.escape(str(x))


db = get_db(_db_path())
ss = st.session_state
ss.setdefault("chats", {})
ss.setdefault("prompts", {})
ss.setdefault("page", PAGES[0])


def flash(kind: str, msg: str):
    ss["flash"] = (kind, msg)


# ---------------------------------------------------------------------------
# callbacks (they run before the page is drawn, so they may change widget values)
# ---------------------------------------------------------------------------
def cb_ask(q: str):
    ss["pending_q"] = q


def cb_ask_and_open(q: str):
    ss["pending_q"] = q
    ss["page"] = "Copilot"


def cb_overview_submit():
    q = (ss.get("ov_q") or "").strip()
    if q:
        ss["pending_q"] = q
    ss["ov_q"] = ""


def _select_new_run(run_id: int, what: str):
    ss["run_sel"] = run_id
    ss["page"] = "Overview"
    flash("success", f"{what} analysed and saved as run #{run_id}.")


def cb_demo():
    from netmind.capture.records import to_frame
    from netmind.capture.synthetic import generate_scenario
    events = None if ss.get("demo_events", True) else []
    dur = float(ss.get("demo_duration", 180))
    recs, _ = generate_scenario(duration=dur, seed=int(ss.get("demo_seed", 7)), events=events)
    name = "Synthetic demo" if events is None else "Synthetic normal traffic"
    try:
        rid = analyze_packets(to_frame(recs), name, "synthetic", db, train_until=min(60.0, dur * 0.33))
        _select_new_run(rid, name)
    except ValueError as e:
        flash("error", f"Could not analyse the demo: {e}")


def cb_upload():
    up = ss.get("upload")
    if up is None:
        flash("error", "Choose a .pcap, .pcapng or NS2 .tr file first.")
        return
    suffix = Path(up.name).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(up.getvalue())
    try:
        if suffix == ".tr":
            rid = analyze_ns2(f.name, up.name, db)
        else:
            from netmind.capture.sniffer import read_pcap
            rid = analyze_packets(read_pcap(f.name), up.name, "pcap", db)
        _select_new_run(rid, up.name)
    except ImportError:
        flash("error", "Reading pcap files needs Scapy: python -m pip install scapy")
    except ValueError as e:
        flash("error", f"Could not analyse {up.name}: {e}")


def cb_capture():
    try:
        from netmind.capture.sniffer import live_capture
    except ImportError:
        flash("error", "Live capture needs Scapy: python -m pip install scapy")
        return
    try:
        df = live_capture(ss.get("cap_iface") or None, timeout=int(ss.get("cap_secs", 30)))
        rid = analyze_packets(df, "Live capture", "live", db)
        _select_new_run(rid, "Live capture")
    except ValueError as e:
        flash("error", f"Capture finished but could not be analysed: {e}")
    except Exception as e:  # permissions, missing Npcap, wrong interface
        flash("error", f"Live capture failed ({type(e).__name__}: {e}). It needs Npcap and a "
                       "terminal started as Administrator; you can also use "
                       "`python -m netmind capture` and then pick the run here.")


def cb_delete(run_id: int):
    db.delete_run(run_id)
    ss.pop("run_sel", None)
    ss["chats"].pop(run_id, None)
    flash("success", f"Run #{run_id} deleted.")


# ---------------------------------------------------------------------------
# sidebar
# ---------------------------------------------------------------------------
runs = db.runs()
run_ids = [int(r) for r in runs["id"]] if not runs.empty else []
if ss.get("run_sel") not in run_ids:
    ss.pop("run_sel", None)

with st.sidebar:
    st.markdown(BRAND, unsafe_allow_html=True)
    if run_ids:
        labels = {int(r.id): f"#{r.id}  {r.name}" for r in runs.itertuples()}
        st.selectbox("Run", run_ids, format_func=labels.get, key="run_sel")
        st.radio("Page", PAGES, key="page", label_visibility="collapsed")
    with st.expander("Start a new run", expanded=not run_ids):
        st.markdown("**Synthetic demo**")
        st.toggle("Inject congestion, port scan and ping flood", value=True, key="demo_events")
        c1, c2 = st.columns(2)
        c1.number_input("Seed", min_value=0, max_value=9999, value=7, step=1, key="demo_seed")
        c2.number_input("Seconds", min_value=60, max_value=600, value=180, step=20, key="demo_duration",
                       help="At least 60 s: the first third is used to learn what normal looks like")
        stretch(st.button, "Generate and analyse", on_click=cb_demo, type="primary", key="btn_demo")
        st.divider()
        st.markdown("**Analyse a file**")
        st.file_uploader("pcap, pcapng or NS2 trace", type=["pcap", "pcapng", "cap", "tr"],
                         key="upload")
        stretch(st.button, "Analyse file", on_click=cb_upload, key="btn_upload")
        st.divider()
        st.markdown("**Live capture**")
        st.caption("Needs Scapy, Npcap and a terminal run as Administrator. Only capture "
                   "networks you are allowed to monitor.")
        c3, c4 = st.columns(2)
        c3.number_input("Seconds", min_value=10, max_value=300, value=30, step=10, key="cap_secs")
        c4.text_input("Interface", placeholder="default", key="cap_iface")
        stretch(st.button, "Capture and analyse", on_click=cb_capture, key="btn_capture")

if "flash" in ss:
    kind, msg = ss.pop("flash")
    (st.success if kind == "success" else st.error)(msg)

if not run_ids:
    st.markdown('<div class="nm-title">Welcome to NetMind</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="nm-empty">There are no runs yet. Open <b>Start a new run</b> in the sidebar '
        'and choose <b>Generate and analyse</b> to analyse synthetic traffic with three known '
        'problems, or analyse a pcap or NS2 trace file.</div>', unsafe_allow_html=True)
    st.stop()

run_id = int(ss["run_sel"]) if "run_sel" in ss else run_ids[0]
state = get_state(db, run_id)
metrics = db.load("metrics", run_id)
scores = db.load("anomalies", run_id)
incidents = state["incidents"]
summary = state.get("summary", {})
is_ns2 = state["run"]["source"] == "ns2"
is_synth = state["run"]["source"] in ("synthetic", "demo")
summ_full = db.run(run_id)["summary"]

for c in ("t", "pps", "latency_ms", "loss_pct", "throughput_mbps", "jitter_ms"):
    if c not in metrics.columns:
        metrics[c] = float("nan")
for c, d in (("anomaly_score", float("nan")), ("max_deviation", float("nan")), ("is_anomaly", False)):
    if c not in scores.columns:
        scores[c] = d
if "t" not in scores.columns:
    scores["t"] = metrics["t"]


def header(title: str | None = None):
    """Run title, source tag and the verdict, at the top of every page."""
    verdict, tone = logic.verdict(state, summary.get("duration_s"))
    tag = ('<span class="nm-tag synthetic">synthetic</span>' if is_synth else
           f'<span class="nm-tag">{esc(state["run"]["source"])}</span>')
    meta = (f'Run #{run_id} &nbsp; {summary.get("packets", 0):,} packets &nbsp; '
            f'{summary.get("duration_s", 0):g} s &nbsp; {summary.get("hosts", 0)} hosts &nbsp; '
            f'{summary.get("flows", 0):,} flows')
    st.markdown(
        f'<div class="nm-head"><div><div class="nm-title">{esc(title or state["run"]["name"])}{tag}</div>'
        f'<div class="nm-meta">{meta}</div></div>'
        f'<div class="nm-verdict {tone}">{esc(verdict)}</div></div>', unsafe_allow_html=True)
    if is_synth:
        st.caption("Synthetic traffic generated by NetMind's demo, not a real capture.")


# ---------------------------------------------------------------------------
# Copilot (shared by the Overview panel and the Copilot page)
# ---------------------------------------------------------------------------
def answer_pending():
    q = ss.pop("pending_q", None)
    if not q:
        return
    res = get_copilot().ask(q, state)
    hist = ss["chats"].setdefault(run_id, [])
    hist.append({"role": "user", "content": q})
    hist.append({"role": "assistant", "content": res["answer"], "backend": res["backend"],
                 "sources": res["sources"]})
    ss["prompts"][run_id] = res["prompt"]


def show_history(limit: int | None = None):
    hist = ss["chats"].get(run_id, [])
    if limit:
        hist = hist[-limit:]
    for m in hist:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m["role"] == "assistant":
                src = "; ".join(f"[{s['n']}] {s['title']}" for s in m.get("sources", []))
                st.caption(f"answered by: {m.get('backend')}" + (f" · sources: {src}" if src else ""))


def copilot_panel():
    st.markdown('<div class="nm-panel-title">Ask the Copilot</div>'
                '<div class="nm-panel-sub">Answers use this run\'s measurements, its incidents and '
                'the networking knowledge base.</div>', unsafe_allow_html=True)
    answer_pending()
    for i, q in enumerate(SUGGESTIONS[:3]):
        stretch(st.button, q, on_click=cb_ask, args=(q,), key=f"ov_sugg_{i}")
    box = st.container(height=430, border=True)
    with box:
        if not ss["chats"].get(run_id):
            st.caption("Pick a question above or type your own below.")
        show_history(limit=6)
    with st.form("ov_form", border=False):
        st.text_input("Your question", key="ov_q", placeholder="e.g. Why did latency jump?",
                      label_visibility="collapsed")
        st.form_submit_button("Ask", on_click=cb_overview_submit, type="primary")


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------
def page_overview():
    header()
    rate_col = "pps"
    chart(charts.network_trace(metrics, incidents, rate_col, "Packets per second"), key="trace")
    st.markdown('<div class="nm-trace-cap">Traffic across the whole run. Red bands are incidents '
                'found by the anomaly detector.</div>', unsafe_allow_html=True)
    st.markdown(logic.kpi_cards_html(logic.kpis(state, metrics, scores)), unsafe_allow_html=True)

    left, right = st.columns([2.15, 1], gap="large")
    with left:
        st.markdown("### Latency and loss over time")
        lat_name = "One-way delay (ms)" if is_ns2 else "Latency (ms)"
        chart(charts.metric_panels(metrics, incidents, state.get("baseline", {}),
                                   [("latency_ms", lat_name), ("loss_pct", "Packet loss (%)")]),
              key="ov_panels")
        c1, c2 = st.columns(2)
        protos = db.load("protocols", run_id)
        with c1:
            st.markdown("### Protocols")
            if not protos.empty:
                p = protos.sort_values("packets")
                chart(charts.hbars(p["protocol"].tolist(), p["packets"].tolist(),
                                   text=[f"{v:g}%" for v in p["share_pct"]], xtitle="packets"),
                      key="ov_protos")
        with c2:
            st.markdown("### Top talkers")
            tt = pd.DataFrame(summ_full.get("top_talkers", []))
            if tt.empty:
                fl = db.load("flows", run_id)
                if not fl.empty:
                    tt = fl.groupby("a")["bytes"].sum().reset_index().rename(columns={"a": "host"}) \
                        .sort_values("bytes", ascending=False).head(5)
            if not tt.empty:
                tt = tt.sort_values("bytes")
                chart(charts.hbars(tt["host"].tolist(), tt["bytes"].tolist(),
                                   text=[f"{b / 1e6:.2f} MB" for b in tt["bytes"]], xtitle="bytes sent"),
                      key="ov_talkers")
        if incidents:
            st.markdown("### Incidents")
            for e in incidents:
                sev, colour = logic.severity(e)
                st.markdown(
                    f'<div class="nm-inc-head"><span class="nm-inc-title">{esc(e["title"])}</span>'
                    f'<span class="nm-sev" style="background:{colour}">{sev}</span>'
                    f'<span class="nm-inc-meta">t = {e["start_t"]:g} to {e["end_t"]:g} s, '
                    f'<b>{esc(e.get("top_src"))}</b> to <b>{esc(e.get("top_dst"))}</b></span></div>',
                    unsafe_allow_html=True)
            st.caption("Details and evidence are on the Incidents page.")
    with right:
        copilot_panel()


def page_incidents():
    header("Incidents")
    status = state.get("anomaly_status") or {}
    if status.get("state") == "insufficient_data":
        st.info(f"Anomaly detection was skipped: {status.get('reason')}.")
        return
    if not incidents:
        st.success("No incidents: every time window looked like the normal baseline.")
        return
    st.markdown("### Anomaly score over time")
    chart(charts.anomaly_chart(scores, summ_full.get("threshold"), incidents), key="inc_score")
    st.caption("A window is flagged when one feature is 6 or more units of normal spread away from "
               "normal, or when the Isolation Forest score is above its threshold and a feature is "
               "4 or more units away.")
    for i, e in enumerate(incidents):
        sev, colour = logic.severity(e)
        with st.container(border=True):
            st.markdown(
                f'<div class="nm-inc-head"><span class="nm-inc-title">{esc(e["title"])}</span>'
                f'<span class="nm-sev" style="background:{colour}">{sev}</span></div>'
                f'<div class="nm-inc-meta">t = {e["start_t"]:g} to {e["end_t"]:g} s '
                f'({e["windows"]:g} windows) &nbsp; peak score {e["peak_score"]:.2f} &nbsp; '
                f'busiest traffic {esc(e.get("top_proto"))} from <b>{esc(e.get("top_src"))}</b> '
                f'to <b>{esc(e.get("top_dst"))}</b></div>', unsafe_allow_html=True)
            c1, c2 = st.columns([1, 1], gap="large")
            feats = e.get("top_features") or []
            with c1:
                if feats:
                    st.markdown("**What stood out**")
                    chart(charts.evidence_bars(feats), key=f"inc_ev_{i}")
            with c2:
                col = next((f["feature"] for f in feats if f["feature"] in metrics.columns
                            and metrics[f["feature"]].notna().any()), "pps")
                st.markdown("**Around the incident**")
                chart(charts.zoom_chart(metrics, e, col, logic.feature_name(col),
                                        state.get("baseline", {}).get(col)), key=f"inc_zoom_{i}")
            q = (f"Explain the {e['title'].lower()} between t={e['start_t']:g} s and "
                 f"t={e['end_t']:g} s. What caused it and what should I check?")
            st.button("Ask the Copilot about this incident", key=f"inc_ask_{i}",
                      on_click=cb_ask_and_open, args=(q,))
    if state.get("routes"):
        st.markdown("### Route changes (NS2)")
        stretch(st.dataframe, pd.DataFrame(state["routes"]).rename(
            columns={"t": "Time (s)", "fid": "Flow", "path": "Path"}), hide_index=True)


def page_traffic():
    header("Traffic")
    protos = db.load("protocols", run_id)
    flows = db.load("flows", run_id)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("### Packets by protocol")
        if not protos.empty:
            p = protos.sort_values("packets")
            chart(charts.hbars(p["protocol"].tolist(), p["packets"].tolist(),
                               text=[f"{v:g}%" for v in p["share_pct"]], xtitle="packets"), key="tr_p")
    with c2:
        st.markdown("### Bytes by protocol")
        if not protos.empty:
            p = protos.sort_values("bytes")
            chart(charts.hbars(p["protocol"].tolist(), p["bytes"].tolist(),
                               text=[f"{b / 1e6:.2f} MB" for b in p["bytes"]], xtitle="bytes"), key="tr_b")
    st.markdown("### Flows")
    st.caption("A flow is one conversation: the same two addresses, two ports and protocol, "
               "both directions together.")
    if flows.empty:
        st.write("No flows stored for this run.")
        return
    lbl = flows["app"].where(flows["app"].fillna("") != "", flows["proto"])
    c3, c4 = st.columns([2, 1])
    text = c3.text_input("Search address, port or protocol", key="flow_q",
                         placeholder="e.g. 192.168.1.66 or :443")
    chosen = c4.multiselect("Protocols", sorted(lbl.dropna().unique()), key="flow_protos")
    shown = logic.filter_flows(flows, text, chosen)
    top = shown.sort_values("bytes", ascending=False).head(10).sort_values("bytes")
    if not top.empty:
        chart(charts.hbars(top["flow"].tolist(), top["bytes"].tolist(),
                           text=[f"{b / 1e3:.0f} kB" for b in top["bytes"]], xtitle="bytes"), key="tr_f")
    cols = [c for c in ("flow", "proto", "app", "packets", "bytes", "duration_s") if c in shown.columns]
    stretch(st.dataframe, shown[cols].sort_values("bytes", ascending=False), hide_index=True,
            height=360, column_config={
                "flow": st.column_config.TextColumn("Flow"),
                "packets": st.column_config.NumberColumn("Packets", format="%d"),
                "bytes": st.column_config.NumberColumn("Bytes", format="%d"),
                "duration_s": st.column_config.NumberColumn("Duration (s)", format="%.2f")})
    st.caption(f"{len(shown):,} of {len(flows):,} flows shown.")


def page_performance():
    header("Performance")
    lat_name = "One-way delay (ms)" if is_ns2 else "Latency (ms)"
    panels = [("latency_ms", lat_name), ("jitter_ms", "Jitter (ms)"), ("loss_pct", "Packet loss (%)"),
              ("throughput_mbps", "Throughput (Mb/s)"), ("pps", "Packets per second"),
              ("retransmissions", "TCP retransmissions")]
    chart(charts.metric_panels(metrics, incidents, state.get("baseline", {}), panels, 140), key="pf_p")
    with st.expander("How these are measured"):
        if is_ns2:
            st.markdown("- **Delay**: receive time minus send time of each delivered packet (NS2 knows "
                        "both).\n- **Loss**: dropped / (delivered + dropped), by the window a packet was "
                        "sent in.\n- **Jitter**: average change in delay between consecutive packets of "
                        "the same flow.")
        else:
            st.markdown("- **Latency**: request-to-reply time from TCP SYN to SYN-ACK, ping request to "
                        "reply, and DNS query to response, averaged per path.\n- **Loss**: (TCP "
                        "retransmissions + unanswered pings) / (TCP data segments + pings).\n- **Jitter**: "
                        "average change between consecutive RTTs on the same path.")
    rtt = db.load("rtt", run_id)
    if not rtt.empty and "kind" in rtt.columns:
        st.markdown("### Round-trip times by measurement type")
        chart(charts.rtt_boxes(rtt), key="pf_rtt")
        st.caption("Log scale. A ping to the gateway takes a few milliseconds; a handshake with a web "
                   "server takes tens.")
    if summ_full.get("ns2_flows"):
        st.markdown("### Per-flow totals (NS2)")
        stretch(st.dataframe, pd.DataFrame(summ_full["ns2_flows"]), hide_index=True)


def page_topology():
    import networkx as nx
    from netmind.topology import (graph_from_frames, link_state_tables, shortest_path)
    header("Topology & routing")
    G = graph_from_frames(db.load("nodes", run_id), db.load("links", run_id))
    if G.number_of_nodes() < 2:
        st.write("Not enough hosts in this run to draw a topology.")
        return
    nodes = sorted(G.nodes)
    links = sorted(tuple(sorted(e)) for e in G.edges)
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
    weight = c1.radio("Cost", ["latency", "hops"], horizontal=True, key="topo_w",
                      help="latency = measured median RTT (ms); hops = every link costs 1")
    src = c2.selectbox("From", nodes, index=0, key="topo_src")
    dst = c3.selectbox("To", nodes, index=len(nodes) - 1, key="topo_dst")
    fail = c4.selectbox("Simulate a link failure", ["None"] + [f"{a} – {b}" for a, b in links],
                        key="topo_fail")
    failed = None if fail == "None" else links[[f"{a} – {b}" for a, b in links].index(fail)]
    H = G.copy()
    if failed:
        H.remove_edge(*failed)
    try:
        sp = shortest_path(H, src, dst, weight)
        path_edges = set(zip(sp["path"], sp["path"][1:]))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        sp, path_edges = None, set()
    chart(charts.topology_chart(G, path_edges, failed), key="topo_chart")
    if sp:
        st.markdown(f"**Dijkstra shortest path ({weight})**: "
                    f"<span class='nm-mono'>{' → '.join(map(esc, sp['path']))}</span>, total cost "
                    f"{sp['cost']:g}" + (" (with the failed link removed)" if failed else ""),
                    unsafe_allow_html=True)
    else:
        st.warning(f"No path from {src} to {dst}" + (" once that link fails." if failed else "."))
    st.caption("Node size shows bytes sent; line width shows packets on the link. This is a logical "
               "map of who talked to whom, not physical cabling.")

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown(f"### Routing table of {src}")
        ls = link_state_tables(G, weight)[src]
        dvt = logic.simulate_link_failure(G, ("", ""), src, weight)
        tab = pd.DataFrame([{"Destination": d, "Next hop (LS)": ls[d]["next_hop"], "Cost (LS)": ls[d]["cost"]}
                            for d in sorted(ls)]).merge(
            dvt[["Destination", "Next hop before", "Cost before"]].rename(
                columns={"Next hop before": "Next hop (DV)", "Cost before": "Cost (DV)"}), on="Destination")
        stretch(st.dataframe, tab, hide_index=True)
        st.caption(f"Link State runs Dijkstra on the full map; Distance Vector exchanges tables with "
                   f"neighbours (Bellman-Ford) and converged in {dvt.attrs['dv_rounds']} rounds. Both "
                   "reach the same costs.")
    with right:
        st.markdown("### After the link failure")
        if not failed:
            st.markdown('<div class="nm-empty">Choose a link under <b>Simulate a link failure</b> to '
                        'see how Distance Vector routing recomputes the routes.</div>',
                        unsafe_allow_html=True)
        else:
            sim = logic.simulate_link_failure(G, failed, src, weight)
            changed = int(sim["Changed"].sum())
            st.markdown(f"Link **{esc(failed[0])} – {esc(failed[1])}** removed: **{changed}** of "
                        f"{len(sim)} routes from {esc(src)} changed. Distance Vector re-converged in "
                        f"{sim.attrs['dv_rounds']} rounds.")
            stretch(st.dataframe, sim, hide_index=True)


def page_copilot():
    header("Copilot")
    cp = get_copilot()
    q = st.chat_input("Ask about this run, e.g. why did latency jump at 70 s?")
    if q:
        ss["pending_q"] = q
    answer_pending()
    left, right = st.columns([2.2, 1], gap="large")
    with right:
        st.markdown("### Try asking")
        for i, s in enumerate(SUGGESTIONS):
            stretch(st.button, s, on_click=cb_ask, args=(s,), key=f"cp_sugg_{i}")
        for i, e in enumerate(incidents[:4]):
            q2 = f"Explain the {e['title'].lower()} between t={e['start_t']:g} s and t={e['end_t']:g} s."
            stretch(st.button, f"Explain: {e['title']} ({e['start_t']:g}-{e['end_t']:g} s)",
                    on_click=cb_ask, args=(q2,), key=f"cp_inc_{i}")
        st.markdown("### Model")
        if cp.backend == "offline":
            st.markdown("Running **offline**: answers are built from the incidents and the knowledge "
                        "base without an LLM. For Claude, set `ANTHROPIC_API_KEY` before starting the "
                        "dashboard; for a free local model, install Ollama and run "
                        "`ollama pull llama3.2`.")
        else:
            st.markdown(f"Using **{esc(cp.backend)}**. If it cannot be reached, answers fall back "
                        "to offline mode.")
        st.caption("The Copilot only explains and recommends. It never changes the network.")
        if ss["chats"].get(run_id):
            st.button("Clear conversation", key="cp_clear",
                      on_click=lambda: ss["chats"].pop(run_id, None))
    with left:
        if not ss["chats"].get(run_id):
            st.markdown('<div class="nm-empty">Ask a question below, or pick one on the right. The '
                        'Copilot reads this run\'s measurements and incidents, retrieves the most '
                        'relevant networking notes, and explains what happened.</div>',
                        unsafe_allow_html=True)
        show_history()
        if ss["prompts"].get(run_id):
            with st.expander("What the Copilot was given for the last question"):
                st.code(ss["prompts"][run_id], language=None)


def page_compare():
    header("Compare runs")
    if len(run_ids) < 2:
        st.markdown('<div class="nm-empty">Create a second run to compare, for example a synthetic '
                    'demo with a different seed, or normal traffic without injected problems '
                    '(sidebar, <b>Start a new run</b>).</div>', unsafe_allow_html=True)
        return
    labels = {int(r.id): f"#{r.id}  {r.name}" for r in runs.itertuples()}
    c1, c2 = st.columns(2)
    a = c1.selectbox("Run A", run_ids, index=0, format_func=labels.get, key="cmp_a")
    b = c2.selectbox("Run B", run_ids, index=1, format_func=labels.get, key="cmp_b")
    sa, sb = get_state(db, a), get_state(db, b)
    stretch(st.dataframe, logic.compare_runs(sa, sb), hide_index=True)
    ma, mb = db.load("metrics", a), db.load("metrics", b)
    na, nb = f"#{a} {sa['run']['name']}", f"#{b} {sb['run']['name']}"
    c3, c4 = st.columns(2, gap="large")
    with c3:
        chart(charts.compare_chart(ma, mb, "latency_ms", na, nb, "Latency / delay (ms)"), key="cmp_l")
    with c4:
        chart(charts.compare_chart(ma, mb, "pps", na, nb, "Packets per second"), key="cmp_p")


def page_data():
    header("Data & export")
    st.markdown("### Download")
    c1, c2, c3, c4 = st.columns(4)
    c1.download_button("Report (Markdown)", logic.run_report_md(state, metrics),
                       file_name=f"netmind_run{run_id}_report.md", mime="text/markdown")
    c2.download_button("Metrics (CSV)", metrics.to_csv(index=False), file_name=f"netmind_run{run_id}_metrics.csv",
                       mime="text/csv")
    c3.download_button("Anomaly scores (CSV)", scores.to_csv(index=False),
                       file_name=f"netmind_run{run_id}_anomalies.csv", mime="text/csv")
    c4.download_button("Incidents (CSV)", db.load("incidents", run_id).to_csv(index=False),
                       file_name=f"netmind_run{run_id}_incidents.csv", mime="text/csv")
    for title, df in (("Per-window metrics", metrics), ("Anomaly scores", scores),
                      ("Flows", db.load("flows", run_id))):
        with st.expander(f"{title} ({len(df):,} rows)"):
            stretch(st.dataframe, df, hide_index=True)
    with st.expander("Normal baseline used by the detector"):
        st.json(state.get("baseline", {}))
    st.markdown("### Delete this run")
    sure = st.checkbox(f"I want to delete run #{run_id} ({state['run']['name']})", key="del_sure")
    st.button("Delete run", key="del_btn", disabled=not sure, on_click=cb_delete, args=(run_id,))


{"Overview": page_overview, "Incidents": page_incidents, "Traffic": page_traffic,
 "Performance": page_performance, "Topology & routing": page_topology, "Copilot": page_copilot,
 "Compare runs": page_compare, "Data & export": page_data}[ss.get("page", "Overview")]()
