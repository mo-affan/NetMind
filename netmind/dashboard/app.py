"""M9 NetMind Dashboard (Streamlit).

Run:  python -m netmind dashboard      (or: streamlit run netmind/dashboard/app.py)

Pages: Overview (with the Copilot panel), Incidents, Traffic, Hosts & services, Performance,
Topology & routing, NS2 lab, Copilot, Compare runs, Data & export. The sidebar picks the run, the page, and starts new runs
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
from netmind.dashboard.theme import BRAND, CSS, THEME_HINT  # noqa: E402
from netmind.pipeline import analyze_ns2, analyze_packets, get_state  # noqa: E402
from netmind.storage import DEFAULT_DB, NetMindDB  # noqa: E402

PAGES = ["Overview", "Incidents", "Traffic", "Hosts & services", "Performance", "Topology & routing",
         "NS2 lab", "Copilot", "Compare runs", "Data & export"]
SUGGESTIONS = ["Why is the network slow?", "Is anyone attacking my network?",
               "Did any link fail?", "What is jitter?", "How healthy is my network?",
               "Which hosts failed to connect?", "Are DNS lookups slow?"]

st.set_page_config(page_title="NetMind", page_icon="🛰️", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _st_version() -> tuple[int, int]:
    """Installed Streamlit version, for compatibility."""
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
    """Draws a Plotly chart full width."""
    stretch(st.plotly_chart, fig, config={"displaylogo": False}, key=key)


def _db_path() -> str:
    # --db from `python -m netmind dashboard`, else NETMIND_DB, else data/netmind.db
    """Database path from --db, NETMIND_DB or data/netmind.db."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--db", default=os.environ.get("NETMIND_DB", str(DEFAULT_DB)))
    a, _ = p.parse_known_args()
    return a.db


@st.cache_resource
def get_db(path: str) -> NetMindDB:
    """Opens the database (cached)"""
    return NetMindDB(path)


@st.cache_resource
def get_copilot():
    """Creates the Copilot once (cached)"""
    from netmind.copilot import Copilot
    return Copilot()


def esc(x) -> str:
    """Escapes text before putting it in HTML."""
    return html.escape(str(x))


db = get_db(_db_path())
ss = st.session_state
ss.setdefault("chats", {})
ss.setdefault("prompts", {})
ss.setdefault("page", PAGES[0])


def flash(kind: str, msg: str):
    """Stores a success or error message for the next refresh."""
    ss["flash"] = (kind, msg)


# ---------------------------------------------------------------------------
# callbacks (they run before the page is drawn, so they may change widget values)
# ---------------------------------------------------------------------------
def cb_ask(q: str):
    """Queues a question for the Copilot."""
    ss["pending_q"] = q


def cb_ask_and_open(q: str):
    """Queues a question and opens the Copilot page."""
    ss["pending_q"] = q
    ss["page"] = "Copilot"


def cb_overview_submit():
    """Sends the question typed in the Overview panel."""
    q = (ss.get("ov_q") or "").strip()
    if q:
        ss["pending_q"] = q
    ss["ov_q"] = ""


def _select_new_run(run_id: int, what: str):
    """Selects a newly made run and opens Overview."""
    ss["run_sel"] = run_id
    ss["page"] = "Overview"
    flash("success", f"{what} analysed and saved as run #{run_id}.")


def cb_demo():
    """Generate and analyse: makes a synthetic demo run."""
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
    """Analyse file: analyses an uploaded pcap or NS2 trace."""
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
    """Capture and analyse: live capture from the sidebar."""
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


def _saved_upload(key: str) -> str | None:
    """Path of a temporary copy of an uploaded file (written once per upload)."""
    up = ss.get(key)
    if up is None:
        return None
    tag = (up.name, up.size)
    cached = ss.get(f"{key}_saved")
    if cached and cached[0] == tag and Path(cached[1]).exists():
        return cached[1]
    with tempfile.NamedTemporaryFile(suffix=Path(up.name).suffix or ".tr", delete=False) as f:
        f.write(up.getvalue())
    ss[f"{key}_saved"] = (tag, f.name)
    return f.name


def cb_ns2_analyse(path: str, name: str):
    """NS2 lab: turns the checked trace into a NetMind run."""
    try:
        rid = analyze_ns2(path, name, db)
        _select_new_run(rid, name)
    except ValueError as e:
        flash("error", f"Could not analyse {name}: {e}")


def cb_delete(run_id: int):
    """Deletes a run and its chat."""
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
        c1.number_input("Seed", min_value=0, max_value=9999, value=7, step=1, key="demo_seed",
                       help="7 is the fixed demo used on the slides (problems at 70, 120 and 150 s). "
                            "Any other seed moves the problems, changes their order and strength, and "
                            "picks a different attacker.")
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
    st.markdown(THEME_HINT, unsafe_allow_html=True)

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
            f'{logic.fmt_seconds(summary.get("duration_s"))} &nbsp; {summary.get("hosts", 0)} hosts &nbsp; '
            f'{summary.get("flows", 0):,} flows')
    st.markdown(
        f'<div class="nm-head"><div><div class="nm-title">{esc(title or state["run"]["name"])}{tag}</div>'
        f'<div class="nm-meta">{meta}</div></div>'
        f'<div class="nm-head-right">{logic.health_badge_html(state.get("health"))}'
        f'<div class="nm-verdict {tone}">{esc(verdict)}</div></div></div>', unsafe_allow_html=True)
    if is_synth:
        st.caption("Synthetic traffic generated by NetMind's demo, not a real capture.")


# ---------------------------------------------------------------------------
# Copilot (shared by the Overview panel and the Copilot page)
# ---------------------------------------------------------------------------
def answer_pending():
    """Answers the queued question and saves it to the chat history."""
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
    """Shows the conversation with backend and sources."""
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
    """The Copilot box on the Overview page."""
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
    """Overview page: traffic trace, KPIs, latency/loss, protocols, Copilot."""
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
    """Incidents page: score chart, one card per incident with evidence."""
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
    """Traffic page: protocols and the searchable flow table."""
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


def page_hosts():
    """Hosts & services page: scanner warning, hosts, connections, DNS."""
    header("Hosts & services")
    inv = db.load("hosts", run_id)
    conn, dns = state.get("connections") or {}, state.get("dns") or {}
    cards = logic.insight_cards(conn, dns)
    if cards:
        st.markdown(logic.kpi_cards_html(cards), unsafe_allow_html=True)
    if conn.get("likely_scanners"):
        f = conn["top_failing"][0]
        st.warning(f"**Likely port scanner: {', '.join(conn['likely_scanners'])}**. {f['client']} made "
                   f"{f['failed']:,} connection attempts that failed, to {f['ports']:,} different ports on "
                   f"{f['targets']} host(s).")
    st.markdown("### Hosts")
    if inv.empty:
        st.markdown('<div class="nm-empty">No host inventory for this run. Runs made before this '
                    'version of NetMind do not have one; analyse the traffic again to get it.</div>',
                    unsafe_allow_html=True)
    else:
        st.caption("Role comes from behaviour: a server answered connections, DNS queries or pings; a "
                   "client started them; a likely scanner had many failed attempts to many ports.")
        c1, c2 = st.columns([1.35, 1], gap="large")
        with c1:
            cols = [c for c in ("host", "scope", "role", "services", "packets_out", "bytes_out",
                                "packets_in", "bytes_in", "peers", "first_seen", "last_seen") if c in inv.columns]
            stretch(st.dataframe, inv[cols], hide_index=True, height=min(420, 38 + 35 * len(inv)),
                    column_config={
                        "host": st.column_config.TextColumn("Host"),
                        "scope": st.column_config.TextColumn("Scope"),
                        "role": st.column_config.TextColumn("Role"),
                        "services": st.column_config.TextColumn("Services answered"),
                        "packets_out": st.column_config.NumberColumn("Packets sent", format="%d"),
                        "bytes_out": st.column_config.NumberColumn("Bytes sent", format="%d"),
                        "packets_in": st.column_config.NumberColumn("Packets received", format="%d"),
                        "bytes_in": st.column_config.NumberColumn("Bytes received", format="%d"),
                        "peers": st.column_config.NumberColumn("Peers", format="%d"),
                        "first_seen": st.column_config.NumberColumn("First seen (s)", format="%.1f"),
                        "last_seen": st.column_config.NumberColumn("Last seen (s)", format="%.1f")})
        with c2:
            chart(charts.host_bytes(inv), key="hs_bytes")
    st.markdown("### TCP connections")
    conns = db.load("connections", run_id)
    if conns.empty:
        st.markdown('<div class="nm-empty">No TCP connection attempts (SYN packets) in this run. NS2 '
                    'traces do not carry TCP flags, so this view is for captures and the demo.</div>',
                    unsafe_allow_html=True)
    else:
        st.caption("Each attempt is followed from its SYN: established = SYN-ACK came back; refused = "
                   "RST came back; unanswered = nothing came back; reset = established, then aborted.")
        c3, c4 = st.columns([1, 1], gap="large")
        with c3:
            chart(charts.outcome_bars(conns), key="hs_outcomes")
        with c4:
            failed = conns[conns["state"].isin(["refused", "unanswered"])]
            st.markdown("**Services**")
            stretch(st.dataframe, logic.service_table(conns), hide_index=True)
            if not failed.empty:
                st.caption(f"{len(failed):,} failed attempts in total.")
        with st.expander(f"All connection attempts ({len(conns):,})"):
            stretch(st.dataframe, conns, hide_index=True, height=360)
        st.button("Ask the Copilot about these connections", key="hs_ask",
                  on_click=cb_ask_and_open, args=("Which hosts failed to connect?",))
    st.markdown("### DNS")
    top = db.load("dns", run_id)
    if top.empty:
        st.markdown('<div class="nm-empty">No DNS lookups in this run.</div>', unsafe_allow_html=True)
    else:
        c5, c6 = st.columns([1, 1], gap="large")
        with c5:
            t = top.sort_values("queries")
            chart(charts.hbars(t["name"].tolist(), t["queries"].tolist(),
                               text=[f"{q:,}" for q in t["queries"]], xtitle="lookups"), key="hs_dns")
        with c6:
            stretch(st.dataframe, top.rename(columns={"name": "Domain", "queries": "Lookups",
                                                      "unanswered": "Unanswered",
                                                      "response_ms": "Median response (ms)"}),
                    hide_index=True)


def page_performance():
    """Performance page: health, latency, jitter, loss, throughput panels."""
    header("Performance")
    lat_name = "One-way delay (ms)" if is_ns2 else "Latency (ms)"
    panels = [("health", "Network health (0-100)"), ("latency_ms", lat_name), ("jitter_ms", "Jitter (ms)"),
              ("loss_pct", "Packet loss (%)"), ("throughput_mbps", "Throughput (Mb/s)"),
              ("pps", "Packets per second"), ("retransmissions", "TCP retransmissions")]
    chart(charts.metric_panels(metrics, incidents, state.get("baseline", {}), panels, 140), key="pf_p")
    with st.expander("How these are measured"):
        st.markdown("- **Health**: each window starts at 100 and loses up to 40 points for latency above "
                    "normal (all 40 at 4x normal), up to 40 for loss (all 40 at 5%) and 20 if the "
                    "anomaly detector flagged it. 90+ is Good, 70-90 Fair, below 70 Poor.")
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
    """Topology & routing page: graph, Dijkstra, LS vs DV, link failure."""
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


def page_ns2():
    """NS2 lab page: topology, TCL script, how to run, checks, RED comparison."""
    from netmind.dashboard import ns2lab
    header("NS2 lab")
    st.caption("The NS2 Simulation Module: the scenario, its TCL code, how to run it, and the lab checks "
               "applied to a trace. The checks are the same code as ns2/check_trace.py.")
    prm = ns2lab.scenario_parameters()
    c1, c2 = st.columns([1.1, 1], gap="large")
    with c1:
        st.markdown("### Topology")
        chart(charts.ns2_topology(prm["links"]), key="ns2_topo")
        st.caption(f"Routing: {prm['routing']}. Bottleneck n2-n3 queue limit {prm['queue_limit']} packets; "
                   f"backup links cost {', '.join(str(c) for *_, c in prm['costs'])}, so traffic uses n4 only "
                   f"when n2-n3 is down. TCP window {prm['tcp_window']} packets; UDP {prm['udp_rate']}.")
    with c2:
        st.markdown("### Timeline")
        stretch(st.dataframe, pd.DataFrame(ns2lab.TIMELINE, columns=["Time", "Event", "Expected"]),
                hide_index=True)
    t_code, t_run, t_check, t_cmp = st.tabs(["TCL script", "How to run", "Check a trace", "DropTail vs RED"])
    with t_code:
        src = ns2lab.scenario_source()
        st.download_button("Download netmind_scenario.tcl", src, file_name="netmind_scenario.tcl",
                           mime="text/plain", key="ns2_dl")
        st.code(src, language="tcl", line_numbers=True)
    with t_run:
        st.markdown("Run these in the **Ubuntu** terminal (not PowerShell). NS2 writes the trace "
                    "(`.tr`) and the NAM animation (`.nam`) to the folder you run it from.")
        st.code(ns2lab.COMMANDS, language="bash")
        st.markdown("Expected first line: `NetMind NS2 scenario: running 10 s simulation, output base name "
                    "'netmind', bottleneck queue DropTail`, then one line per event and "
                    "`Simulation finished at t=10 s`.")
    with t_check:
        src_kind = st.radio("Trace", ["Upload a trace (.tr)", "Bundled sample trace (synthetic, not NS2 output)"],
                            key="ns2_src", horizontal=True)
        if src_kind.startswith("Upload"):
            st.file_uploader("NS2 trace written by $ns trace-all", type=["tr"], key="ns2_trace")
            path, name = _saved_upload("ns2_trace"), getattr(ss.get("ns2_trace"), "name", None)
        else:
            path, name = str(ns2lab.SAMPLE_TRACE), "sample_ns2.tr"
        if not path:
            st.markdown('<div class="nm-empty">Upload <b>netmind.tr</b> from your Ubuntu folder '
                        '(<code>~/netmind_ns2</code>) to run the five scenario checks on it.</div>',
                        unsafe_allow_html=True)
        else:
            try:
                res = ns2lab.check(path)
            except ValueError as e:
                st.error(f"{name}: {e}")
                res = None
            if res:
                tone = "ok" if res["passed"] == 5 else "bad"
                st.markdown(f'<div class="nm-verdict {tone}" style="display:inline-block">'
                            f'{res["passed"]} of 5 checks passed</div>', unsafe_allow_html=True)
                st.markdown("".join(
                    f'<div class="nm-check {"ok" if ok else "bad"}"><b>{"PASS" if ok else "FAIL"}</b>'
                    f'<span>{esc(n)}</span></div>' for n, ok in res["checks"]), unsafe_allow_html=True)
                s = res["stats"]
                st.markdown(logic.kpi_cards_html([
                    {"label": "Delay, normal period", "value": f"{s['delay_normal_ms']:.1f} ms",
                     "note": "0.5-3 s", "tone": "muted", "series": []},
                    {"label": "Delay, UDP burst", "value": f"{s['delay_burst_ms']:.1f} ms",
                     "note": "3-6 s", "tone": "bad" if s["delay_burst_ms"] > 1.3 * s["delay_normal_ms"] else "muted",
                     "series": []},
                    {"label": "Drops, normal / burst", "value": f"{s['drops_normal']} / {s['drops_burst']}",
                     "note": "data packets", "tone": "muted", "series": []},
                    {"label": "TCP delay, link down", "value": f"{s['delay_failure_ms']:.1f} ms",
                     "note": "via n4, 7.1-8.4 s", "tone": "muted", "series": []}]), unsafe_allow_html=True)
                c3, c4 = st.columns(2, gap="large")
                with c3:
                    st.markdown("**Routes** (a new row each time a flow changed path)")
                    stretch(st.dataframe, pd.DataFrame(res["routes"]).rename(
                        columns={"t": "Time (s)", "fid": "Flow", "path": "Path"}), hide_index=True)
                with c4:
                    st.markdown("**Per phase**")
                    stretch(st.dataframe, ns2lab.phases(path), hide_index=True)
                    st.caption(f"{res['events']:,} packet events, {res['packets']:,} data packets, last "
                               f"event at {res['t_end']:.2f} s. Drops per link: "
                               f"{res['drops_per_link'] or 'none'}.")
                st.button(f"Analyse {name} as a NetMind run", key="ns2_analyse", type="primary",
                          on_click=cb_ns2_analyse, args=(path, name))
    with t_cmp:
        st.markdown("Upload the DropTail trace and the RED trace (`ns netmind_scenario.tcl red RED`) to compare "
                    "them phase by phase, like `compare_traces.py`.")
        c5, c6 = st.columns(2)
        c5.file_uploader("Trace A (DropTail, e.g. netmind.tr)", type=["tr"], key="ns2_a")
        c6.file_uploader("Trace B (RED, e.g. red.tr)", type=["tr"], key="ns2_b")
        pa, pb = _saved_upload("ns2_a"), _saved_upload("ns2_b")
        if not (pa and pb):
            st.markdown('<div class="nm-empty">Choose both traces to see the comparison.</div>',
                        unsafe_allow_html=True)
        else:
            try:
                cmp = ns2lab.compare(pa, pb, "A", "B")
            except (ValueError, SystemExit) as e:
                st.error(f"Could not compare the traces: {e}")
                cmp = None
            if cmp is not None:
                burst = cmp.set_index("Phase").loc["UDP burst"]
                st.markdown(f"During the UDP burst, mean delay is **{burst['Delay (ms) A']:.1f} ms** with A and "
                            f"**{burst['Delay (ms) B']:.1f} ms** with B ({burst['Delay change %']:+.1f}%); drops "
                            f"{int(burst['Drops A'])} vs {int(burst['Drops B'])}.")
                chart(charts.phase_delay_bars(cmp, "A", "B"), key="ns2_cmp_chart")
                stretch(st.dataframe, cmp, hide_index=True)
                st.caption("RED drops early, at random, once the average queue passes its lower threshold, "
                           "so the queue stays shorter than with DropTail, which drops only when it is full.")


def page_copilot():
    """Copilot page: chat, suggestions, model and the exact prompt."""
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
    """Compare runs page: two runs side by side."""
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
    """Data & export page: downloads, raw tables, delete."""
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
                      ("Flows", db.load("flows", run_id)), ("Hosts", db.load("hosts", run_id)),
                      ("TCP connections", db.load("connections", run_id))):
        with st.expander(f"{title} ({len(df):,} rows)"):
            stretch(st.dataframe, df, hide_index=True)
    with st.expander("Normal baseline used by the detector"):
        st.json(state.get("baseline", {}))
    st.markdown("### Delete this run")
    sure = st.checkbox(f"I want to delete run #{run_id} ({state['run']['name']})", key="del_sure")
    st.button("Delete run", key="del_btn", disabled=not sure, on_click=cb_delete, args=(run_id,))


{"Overview": page_overview, "Incidents": page_incidents, "Traffic": page_traffic,
 "Hosts & services": page_hosts,
 "Performance": page_performance, "Topology & routing": page_topology, "NS2 lab": page_ns2, "Copilot": page_copilot,
 "Compare runs": page_compare, "Data & export": page_data}[ss.get("page", "Overview")]()
