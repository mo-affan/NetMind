"""Plotly figures for the dashboard. One style for every chart: thin 2 px lines, recessive
grid, blue for data, red reserved for incidents, grey dashed line for the normal baseline."""
from __future__ import annotations

import math

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"   # validated categorical slots 1-3
RED = "#d03b3b"                                          # status: critical (incidents only)
# Theme-neutral greys: readable on the light and the dark theme. Text colours are left unset so
# Streamlit's chart theme supplies the right one for the theme the viewer picked.
MUTED, GRID, AXIS = "#8794a0", "rgba(128,128,128,0.20)", "rgba(128,128,128,0.45)"
TEAL = "#17a2ac"                                         # highlighted route
CLEAR = "rgba(0,0,0,0)"
OUTLINE = "rgba(255,255,255,0.9)"
FONT = "IBM Plex Sans, Segoe UI, system-ui, sans-serif"
KIND_COLOURS = {"local": BLUE, "gateway": ORANGE, "remote": AQUA, "ns2-node": BLUE}
KIND_NAMES = {"local": "Local host", "gateway": "Gateway", "remote": "Remote server",
              "ns2-node": "NS2 node"}


def style(fig: go.Figure, height: int, legend: bool = False) -> go.Figure:
    """Common chart look: size, margins, font, transparent background."""
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=28, b=8), plot_bgcolor=CLEAR,
                      paper_bgcolor=CLEAR, font=dict(family=FONT, size=12),
                      hoverlabel=dict(font=dict(family=FONT)),
                      showlegend=legend, hovermode="x unified",
                      legend=dict(orientation="h", y=1.08, x=0, font=dict(size=12)))
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickcolor=AXIS, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=AXIS)
    return fig


def _bands(fig, incidents, row=None, labels=True):
    """Draws the red incident bands on a chart."""
    for e in incidents:
        kw = dict(row=row, col=1) if row else {}
        fig.add_vrect(x0=e["start_t"], x1=e["end_t"], fillcolor=RED, opacity=0.13, line_width=0,
                      layer="below", **kw)
        if labels:
            fig.add_annotation(x=(e["start_t"] + e["end_t"]) / 2, y=1.0, yref="paper",
                               text=e["title"], showarrow=False, yanchor="bottom",
                               font=dict(size=11, color=RED))


def network_trace(metrics: pd.DataFrame, incidents: list[dict], col: str = "pps",
                  name: str = "Packets per second") -> go.Figure:
    """The hero strip: traffic over the whole run with incidents marked."""
    fig = go.Figure(go.Scatter(x=metrics["t"], y=metrics[col], mode="lines", name=name,
                               line=dict(color=BLUE, width=2), fill="tozeroy",
                               fillcolor="rgba(42,120,214,0.10)",
                               hovertemplate=f"{name}: %{{y:.1f}}<extra></extra>"))
    _bands(fig, incidents)
    style(fig, 210)
    fig.update_layout(margin=dict(l=8, r=8, t=26, b=8))
    fig.update_xaxes(title_text="time (s)", title_font=dict(size=11, color=MUTED))
    return fig


def metric_panels(metrics: pd.DataFrame, incidents: list[dict], baseline: dict,
                  panels: list[tuple[str, str]], height_each: int = 150) -> go.Figure:
    """Small multiples sharing the time axis, one measure per panel, normal level dashed."""
    panels = [(c, n) for c, n in panels if c in metrics.columns and metrics[c].notna().any()]
    if not panels:
        return style(go.Figure(), 120)
    fig = make_subplots(rows=len(panels), cols=1, shared_xaxes=True, vertical_spacing=0.16 if len(panels) <= 2 else 0.07,
                        subplot_titles=[n for _, n in panels])
    for a in fig.layout.annotations:  # panel titles
        a.font = dict(size=12, family=FONT)
        a.x, a.xanchor = 0, "left"
    for i, (c, n) in enumerate(panels, 1):
        fig.add_trace(go.Scatter(x=metrics["t"], y=metrics[c], mode="lines", name=n,
                                 line=dict(color=BLUE, width=2),
                                 hovertemplate=f"{n}: %{{y:.2f}}<extra></extra>"), row=i, col=1)
        b = baseline.get(c)
        if b is not None and not (isinstance(b, float) and math.isnan(b)):
            fig.add_hline(y=b, line=dict(color=MUTED, width=1, dash="dash"), row=i, col=1,
                          annotation_text="normal", annotation_position="top left",
                          annotation_font=dict(size=10, color=MUTED))
        _bands(fig, incidents, row=i, labels=False)
    style(fig, 40 + height_each * len(panels))
    fig.update_xaxes(title_text="time (s)", row=len(panels), col=1,
                     title_font=dict(size=11, color=MUTED))
    return fig


def anomaly_chart(scores: pd.DataFrame, threshold: float | None, incidents: list[dict]) -> go.Figure:
    """Anomaly score over time with the threshold line."""
    fig = go.Figure()
    if "anomaly_score" in scores.columns and scores["anomaly_score"].notna().any():
        fig.add_trace(go.Scatter(x=scores["t"], y=scores["anomaly_score"], mode="lines",
                                 name="Anomaly score", line=dict(color=BLUE, width=2),
                                 hovertemplate="score %{y:.2f}<extra></extra>"))
        flagged = scores[scores["is_anomaly"].astype(bool)]
        fig.add_trace(go.Scatter(x=flagged["t"], y=flagged["anomaly_score"], mode="markers",
                                 name="Flagged window",
                                 marker=dict(color=RED, size=9, line=dict(color=OUTLINE, width=2)),
                                 hovertemplate="flagged, score %{y:.2f}<extra></extra>"))
        if threshold:
            fig.add_hline(y=threshold, line=dict(color=MUTED, width=1, dash="dash"),
                          annotation_text="forest threshold", annotation_position="top left",
                          annotation_font=dict(size=10, color=MUTED))
    _bands(fig, incidents, labels=False)
    style(fig, 220, legend=True)
    fig.update_xaxes(title_text="time (s)", title_font=dict(size=11, color=MUTED))
    return fig


def hbars(labels, values, text=None, height=None, colour=BLUE, xtitle="") -> go.Figure:
    """Horizontal bar chart (protocols, talkers, DNS names)"""
    fig = go.Figure(go.Bar(x=values, y=labels, orientation="h", marker=dict(color=colour),
                           text=text, textposition="outside", textfont=dict(size=11),
                           cliponaxis=False, hovertemplate="%{y}: %{x:,}<extra></extra>"))
    style(fig, height or (50 + 34 * len(labels)))
    fig.update_layout(hovermode="closest", margin=dict(l=8, r=40, t=10, b=8))
    fig.update_xaxes(title_text=xtitle, title_font=dict(size=11, color=MUTED), showgrid=True,
                     gridcolor=GRID)
    fig.update_yaxes(showgrid=False, tickfont=dict(size=12))
    return fig


def evidence_bars(features: list[dict]) -> go.Figure:
    """How far each stand-out feature was from normal, in units of normal spread."""
    from netmind.dashboard.logic import feature_name
    f = sorted(features, key=lambda x: abs(x["z"]))
    labels = [feature_name(x["feature"]) for x in f]
    text = [f"{x['value']:g} vs {x['normal']:g} normal" for x in f]
    fig = hbars(labels, [abs(x["z"]) for x in f], text=text, colour=RED,
                xtitle="units of normal spread away from normal")
    fig.update_traces(hovertemplate="%{y}: %{x:.1f} units<extra></extra>")
    return fig


def zoom_chart(metrics: pd.DataFrame, incident: dict, col: str, name: str,
               baseline: float | None) -> go.Figure:
    """One feature zoomed around an incident, normal level dashed."""
    span = incident["end_t"] - incident["start_t"]
    lo, hi = incident["start_t"] - max(10, span), incident["end_t"] + max(10, span)
    m = metrics[(metrics["t"] >= lo) & (metrics["t"] <= hi)]
    fig = go.Figure(go.Scatter(x=m["t"], y=m[col], mode="lines+markers", name=name,
                               line=dict(color=BLUE, width=2), marker=dict(size=6, color=BLUE),
                               hovertemplate=f"{name}: %{{y:.2f}}<extra></extra>"))
    if baseline is not None:
        fig.add_hline(y=baseline, line=dict(color=MUTED, width=1, dash="dash"),
                      annotation_text="normal", annotation_position="top left",
                      annotation_font=dict(size=10, color=MUTED))
    _bands(fig, [incident], labels=False)
    style(fig, 200)
    fig.update_layout(title=dict(text=name, font=dict(size=12), x=0, y=0.98))
    return fig


def rtt_boxes(rtt: pd.DataFrame) -> go.Figure:
    """RTT distribution per type: handshake, ping, DNS (log scale)"""
    names = {"tcp_handshake": "TCP handshake", "icmp_echo": "Ping (ICMP)", "dns": "DNS lookup"}
    fig = go.Figure()
    for kind, n in names.items():
        part = rtt[rtt["kind"] == kind]["rtt_ms"]
        if len(part):
            fig.add_trace(go.Box(x=part, name=n, orientation="h", marker=dict(color=BLUE, size=3),
                                 line=dict(color=BLUE, width=1.5), fillcolor="rgba(42,120,214,0.15)",
                                 boxpoints="outliers", hovertemplate="%{x:.1f} ms<extra></extra>"))
    style(fig, 80 + 60 * len(fig.data))
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(title_text="round-trip time (ms)", type="log", showgrid=True, gridcolor=GRID,
                     title_font=dict(size=11, color=MUTED))
    return fig


def compare_chart(m1: pd.DataFrame, m2: pd.DataFrame, col: str, n1: str, n2: str,
                  title: str) -> go.Figure:
    """One measure of two runs on the same axes."""
    fig = go.Figure()
    for m, n, c in ((m1, n1, BLUE), (m2, n2, ORANGE)):
        if col in m.columns:
            fig.add_trace(go.Scatter(x=m["t"], y=m[col], mode="lines", name=n,
                                     line=dict(color=c, width=2)))
    style(fig, 240, legend=True)
    fig.update_layout(title=dict(text=title, font=dict(size=12), x=0, y=0.98),
                      margin=dict(l=8, r=8, t=56, b=8), legend=dict(y=1.18))
    fig.update_xaxes(title_text="time (s)", title_font=dict(size=11, color=MUTED))
    return fig


def topology_chart(G: nx.Graph, path_edges: set = frozenset(), failed: tuple | None = None,
                   seed: int = 3) -> go.Figure:
    """The host graph, shortest path highlighted, failed link marked."""
    pos = nx.kamada_kawai_layout(G) if G.number_of_nodes() > 2 else nx.spring_layout(G, seed=seed)
    fig = go.Figure()
    max_pk = max([d.get("packets", 1) for _, _, d in G.edges(data=True)] or [1])
    for a, b, d in G.edges(data=True):
        on = (a, b) in path_edges or (b, a) in path_edges
        is_failed = failed is not None and {a, b} == set(failed)
        w = 1 + 4 * math.sqrt(d.get("packets", 1) / max_pk)
        fig.add_trace(go.Scatter(
            x=[pos[a][0], pos[b][0]], y=[pos[a][1], pos[b][1]], mode="lines", hoverinfo="skip",
            line=dict(color=RED if is_failed else (TEAL if on else AXIS),
                      width=3.5 if on else w, dash="dot" if is_failed else "solid")))
    # invisible midpoint markers carry the link tooltips
    tips, mx, my = [], [], []
    for a, b, d in G.edges(data=True):
        mx.append((pos[a][0] + pos[b][0]) / 2)
        my.append((pos[a][1] + pos[b][1]) / 2)
        extra = f"<br>drops: {d['drops']}" if "drops" in d and d["drops"] == d["drops"] else ""
        lat = d.get("latency")
        lat_t = f"{lat:g} ms" + ("" if d.get("measured", True) else " (not measured)") if lat is not None else "?"
        tips.append(f"<b>{a} – {b}</b><br>{int(d.get('packets', 0)):,} packets<br>latency {lat_t}{extra}")
    fig.add_trace(go.Scatter(x=mx, y=my, mode="markers", marker=dict(size=16, opacity=0),
                             hovertext=tips, hoverinfo="text", showlegend=False))
    sent = {n: G.nodes[n].get("bytes_sent", 0) or 0 for n in G.nodes}
    max_s = max(sent.values()) or 1
    for kind in sorted({G.nodes[n].get("kind", "local") for n in G.nodes}):
        ns = [n for n in G.nodes if G.nodes[n].get("kind", "local") == kind]
        fig.add_trace(go.Scatter(
            x=[pos[n][0] for n in ns], y=[pos[n][1] for n in ns], mode="markers+text",
            name=KIND_NAMES.get(kind, kind), text=ns, textposition="top center",
            textfont=dict(size=11, family="IBM Plex Mono, Consolas, monospace"),
            marker=dict(size=[16 + 18 * math.sqrt(sent[n] / max_s) for n in ns],
                        color=KIND_COLOURS.get(kind, BLUE), line=dict(color=OUTLINE, width=2)),
            hovertemplate="<b>%{text}</b><extra>" + KIND_NAMES.get(kind, kind) + "</extra>"))
    for t in fig.data[:-1]:
        t.showlegend = False
    style(fig, 480, legend=True)
    fig.update_layout(hovermode="closest", legend=dict(orientation="h", y=-0.04, x=0))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    # every node-kind trace keeps its legend entry
    for t in fig.data:
        if t.mode == "markers+text":
            t.showlegend = True
    return fig


OUTCOME_COLOURS = {"established": BLUE, "reset": AQUA, "refused": ORANGE, "unanswered": MUTED}


def outcome_bars(conns: pd.DataFrame, top: int = 8) -> go.Figure:
    """TCP connection outcomes per client (stacked), clients with the most attempts first."""
    if conns.empty:
        return style(go.Figure(), 120)
    t = conns.groupby(["client", "state"]).size().unstack(fill_value=0)
    t = t.loc[t.sum(axis=1).sort_values(ascending=False).head(top).index].iloc[::-1]
    fig = go.Figure()
    for state in ("established", "reset", "refused", "unanswered"):
        if state in t.columns:
            fig.add_trace(go.Bar(y=t.index, x=t[state], orientation="h", name=state,
                                 marker=dict(color=OUTCOME_COLOURS[state]),
                                 hovertemplate="%{y}: %{x:,} " + state + "<extra></extra>"))
    style(fig, 70 + 34 * len(t), legend=True)
    fig.update_layout(barmode="stack", hovermode="closest", margin=dict(l=8, r=8, t=36, b=8))
    fig.update_xaxes(title_text="connection attempts", title_font=dict(size=11, color=MUTED),
                     showgrid=True, gridcolor=GRID)
    fig.update_yaxes(showgrid=False, tickfont=dict(size=12, family="IBM Plex Mono, Consolas, monospace"))
    return fig


def host_bytes(inv: pd.DataFrame, top: int = 10) -> go.Figure:
    """Bytes sent and received per host, busiest first."""
    if inv.empty:
        return style(go.Figure(), 120)
    t = inv.head(top).iloc[::-1]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=t["host"], x=t["bytes_out"], orientation="h", name="sent",
                         marker=dict(color=BLUE), hovertemplate="%{y} sent %{x:,} bytes<extra></extra>"))
    fig.add_trace(go.Bar(y=t["host"], x=t["bytes_in"], orientation="h", name="received",
                         marker=dict(color=ORANGE), hovertemplate="%{y} received %{x:,} bytes<extra></extra>"))
    style(fig, 80 + 40 * len(t), legend=True)
    fig.update_layout(barmode="group", hovermode="closest", margin=dict(l=8, r=8, t=36, b=8))
    fig.update_xaxes(title_text="bytes", title_font=dict(size=11, color=MUTED), showgrid=True, gridcolor=GRID)
    fig.update_yaxes(showgrid=False, tickfont=dict(size=12, family="IBM Plex Mono, Consolas, monospace"))
    return fig


NS2_POS = {"n0": (0.0, 1.0), "n1": (0.0, -1.0), "n2": (1.2, 0.0), "n3": (3.0, 0.0), "n4": (2.1, -1.2)}
NS2_ROLE = {"n0": "TCP source", "n1": "UDP source", "n2": "router", "n3": "sink", "n4": "backup"}


def ns2_topology(links: list[dict], down: bool = False) -> go.Figure:
    """The NS2 scenario's five nodes and links, labels taken from the TCL file.
    The n2-n3 bottleneck is red; the backup path through n4 is dashed (solid when `down`)."""
    fig = go.Figure()
    for lk in links:
        a, b = lk["a"], lk["b"]
        if a not in NS2_POS or b not in NS2_POS:
            continue
        (x0, y0), (x1, y1) = NS2_POS[a], NS2_POS[b]
        main = {a, b} == {"n2", "n3"}
        backup = "n4" in (a, b)
        colour = RED if main else (TEAL if backup else AXIS)
        dash = "dot" if main and down else ("dash" if backup and not down else "solid")
        fig.add_trace(go.Scatter(x=[x0, x1], y=[y0, y1], mode="lines", hoverinfo="skip",
                                 line=dict(color=colour, width=5 if main else 3, dash=dash), showlegend=False))
        queue = "DropTail or RED" if lk["queue"].startswith("$") else lk["queue"]
        fig.add_annotation(x=(x0 + x1) / 2, y=(y0 + y1) / 2, text=f"{lk['bandwidth']}, {lk['delay']}"
                           + (f"<br>{queue}" if main else ""), showarrow=False, yshift=16 if not backup else -18,
                           font=dict(size=12, color=RED if main else MUTED))
    xs = [NS2_POS[n][0] for n in NS2_POS]
    ys = [NS2_POS[n][1] for n in NS2_POS]
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers+text", text=list(NS2_POS), textposition="middle center",
        textfont=dict(color="#ffffff", size=14, family="IBM Plex Mono, Consolas, monospace"),
        marker=dict(size=44, color=[BLUE, BLUE, TEAL, BLUE, TEAL], line=dict(color=OUTLINE, width=2)),
        hovertext=[f"{n}: {NS2_ROLE[n]}" for n in NS2_POS], hoverinfo="text", showlegend=False))
    for n, (x, y) in NS2_POS.items():
        fig.add_annotation(x=x, y=y, text=NS2_ROLE[n], showarrow=False, yshift=-34 if y <= 0 else 34,
                           font=dict(size=12, color=MUTED))
    style(fig, 360)
    fig.update_layout(hovermode="closest", margin=dict(l=8, r=8, t=16, b=8))
    fig.update_xaxes(visible=False, range=[-0.6, 3.6])
    fig.update_yaxes(visible=False, range=[-1.7, 1.5])
    return fig


def phase_delay_bars(cmp: pd.DataFrame, name_a: str, name_b: str) -> go.Figure:
    """Mean one-way delay per scenario phase for two NS2 traces."""
    fig = go.Figure()
    for name, colour in ((name_a, MUTED), (name_b, TEAL)):
        col = f"Delay (ms) {name}"
        fig.add_trace(go.Bar(x=cmp["Phase"], y=cmp[col], name=name, marker=dict(color=colour),
                             text=[f"{v:.1f}" for v in cmp[col]], textposition="outside", cliponaxis=False,
                             hovertemplate="%{x}: %{y:.1f} ms<extra>" + name + "</extra>"))
    style(fig, 300, legend=True)
    fig.update_layout(barmode="group", hovermode="closest", margin=dict(l=8, r=8, t=40, b=8))
    fig.update_yaxes(title_text="mean one-way delay (ms)", title_font=dict(size=11, color=MUTED))
    return fig
