"""Dashboard logic that does not need Streamlit or Plotly (so it can be unit-tested anywhere).

KPIs, incident severity, the share of normal windows, sparklines, the run report, run
comparison and the link-failure simulation used by the Topology page.
"""
from __future__ import annotations

import html
import math

import networkx as nx
import pandas as pd

SEVERITY = [  # (minimum peak deviation, label, colour). Ordered from most severe.
    (30.0, "High", "#d03b3b"),
    (10.0, "Medium", "#e5762e"),
    (0.0, "Low", "#b88600"),
]


def severity(incident: dict) -> tuple[str, str]:
    """(label, colour) from how far the incident's strongest feature was from normal."""
    dev = incident.get("peak_deviation") or 0.0
    if isinstance(dev, float) and math.isnan(dev):
        dev = 0.0
    for limit, label, colour in SEVERITY:
        if dev >= limit:
            return label, colour
    return SEVERITY[-1][1], SEVERITY[-1][2]


def normal_share(scores: pd.DataFrame) -> float | None:
    """Percentage of time windows the detector did NOT flag (None if detection was skipped)."""
    if scores is None or scores.empty or "is_anomaly" not in scores.columns:
        return None
    if "anomaly_score" in scores.columns and scores["anomaly_score"].isna().all():
        return None
    return round(100 * (1 - scores["is_anomaly"].astype(bool).mean()), 1)


def fmt_seconds(s) -> str:
    """179.991 -> "180 s", 7.25 -> "7.3 s" (whole seconds once the run is longer than 10 s)."""
    v = _num(s)
    if v is None:
        return "? s"
    return f"{v:.0f} s" if abs(v) >= 10 else f"{v:.1f}".rstrip("0").rstrip(".") + " s"


def verdict(state: dict, duration_s: float | None) -> tuple[str, str]:
    """Headline sentence and tone ("bad", "ok", "info") for the top of the page."""
    status = state.get("anomaly_status") or {}
    n = len(state.get("incidents", []))
    span = f" in {fmt_seconds(duration_s)}" if duration_s else ""
    if status.get("state") == "insufficient_data":
        return "Not enough traffic to judge yet", "info"
    if n == 0:
        return f"No incidents{span}", "ok"
    return f"{n} incident{'s' if n != 1 else ''}{span}", "bad"


def sparkline_svg(values, width: int = 132, height: int = 34, colour: str = "#2a78d6") -> str:
    """Inline SVG polyline of a series (NaNs skipped). Empty string if fewer than 2 points."""
    pts = [float(v) for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    rng = hi - lo or 1.0
    step = width / (len(pts) - 1)
    coords = " ".join(f"{i * step:.1f},{height - 3 - (v - lo) / rng * (height - 6):.1f}"
                      for i, v in enumerate(pts))
    return (f'<svg class="nm-spark" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            f'role="img" aria-label="trend"><polyline fill="none" stroke="{colour}" '
            f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round" points="{coords}"/></svg>')


def _num(v):
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def kpis(state: dict, metrics: pd.DataFrame, scores: pd.DataFrame) -> list[dict]:
    """Headline numbers: label, value text, note text, note tone, sparkline series."""
    o, base = state.get("overall", {}), state.get("baseline", {})
    ns2 = state.get("run", {}).get("source") == "ns2"
    lat_name = "Delay" if ns2 else "Latency"

    def col(name):
        return metrics[name].tolist() if name in metrics.columns else []

    lat = metrics["latency_ms"] if "latency_ms" in metrics.columns else pd.Series(dtype=float)
    normal_lat = _num(base.get("latency_ms"))
    worst = _num(lat.max()) if len(lat) else None
    cards = [{
        "label": f"Normal {lat_name.lower()}", "value": _fmt(normal_lat, "ms"),
        "note": "median of the baseline period" if normal_lat is not None else "no baseline",
        "tone": "muted", "series": col("latency_ms")}]
    if worst is not None and normal_lat:
        ratio = worst / normal_lat
        cards.append({"label": f"Worst {lat_name.lower()}", "value": _fmt(worst, "ms"),
                      "note": f"{ratio:.1f}x normal", "tone": "bad" if ratio >= 2 else "muted",
                      "series": col("latency_ms")})
    else:
        cards.append({"label": f"Worst {lat_name.lower()}", "value": _fmt(worst, "ms"),
                      "note": "", "tone": "muted", "series": col("latency_ms")})
    loss = _num(o.get("loss_pct"))
    cards.append({"label": "Packet loss", "value": _fmt(loss, "%", 2),
                  "note": "over the whole run", "tone": "bad" if (loss or 0) >= 1 else "muted",
                  "series": col("loss_pct")})
    cards.append({"label": "Throughput", "value": _fmt(_num(o.get("throughput_mbps")), "Mb/s", 3),
                  "note": "average", "tone": "muted", "series": col("throughput_mbps")})
    cards.append({"label": "Jitter", "value": _fmt(_num(o.get("jitter_ms")), "ms"),
                  "note": "per path, averaged", "tone": "muted", "series": col("jitter_ms")})
    share = normal_share(scores)
    cards.append({"label": "Normal windows", "value": "n/a" if share is None else f"{share:g}%",
                  "note": "detection skipped" if share is None else
                  f"of {len(scores)} windows not flagged",
                  "tone": "muted" if share is None or share >= 95 else "bad",
                  "series": scores["anomaly_score"].tolist() if "anomaly_score" in scores.columns else []})
    return cards


def _fmt(v, unit, digits=1):
    return "n/a" if v is None else f"{v:.{digits}f} {unit}"


def kpi_cards_html(cards: list[dict]) -> str:
    out = ['<div class="nm-kpis">']
    for c in cards:
        out.append(
            f'<div class="nm-kpi"><div class="nm-kpi-label">{html.escape(c["label"])}</div>'
            f'<div class="nm-kpi-value">{html.escape(c["value"])}</div>'
            f'<div class="nm-kpi-note nm-{c["tone"]}">{html.escape(c["note"])}</div>'
            f'{sparkline_svg(c["series"])}</div>')
    out.append("</div>")
    return "".join(out)


def feature_name(f: str) -> str:
    return {"pps": "Packets per second", "avg_pkt_size": "Average packet size (bytes)",
            "connections": "Connections", "avg_conn_duration": "Connection duration (s)",
            "dst_ports": "Destination ports", "tcp_udp_ratio": "TCP/UDP ratio",
            "bytes_per_sec": "Bytes per second", "latency_ms": "Latency (ms)",
            "loss_pct": "Packet loss (%)", "retransmissions": "TCP retransmissions",
            "throughput_mbps": "Throughput (Mb/s)", "jitter_ms": "Jitter (ms)"}.get(f, f)


def run_report_md(state: dict, metrics: pd.DataFrame) -> str:
    """A short Markdown report of a run, for download."""
    run, s, o = state["run"], state.get("summary", {}), state.get("overall", {})
    lines = [f"# NetMind report: {run.get('name')}", "",
             f"- Run: #{run.get('id')}, source: {run.get('source')}"]
    if run.get("source") in ("synthetic", "demo"):
        lines.append("- Note: synthetic traffic generated by NetMind's demo, not a real capture")
    lines += [f"- Packets: {s.get('packets')}, bytes: {s.get('bytes')}, duration: {s.get('duration_s')} s, "
              f"hosts: {s.get('hosts')}, flows: {s.get('flows')}",
              f"- Protocols: {s.get('protocols')}", "", "## Overall", ""]
    lines += [f"- {k}: {v}" for k, v in o.items() if v is not None]
    status = state.get("anomaly_status") or {}
    lines += ["", "## Incidents", ""]
    if status.get("state") == "insufficient_data":
        lines.append(f"Anomaly detection skipped: {status.get('reason')}.")
    elif not state.get("incidents"):
        lines.append("None: every window looked like the normal baseline.")
    for e in state.get("incidents", []):
        sev, _ = severity(e)
        lines.append(f"- **{e['title']}** ({sev}), t = {e['start_t']:g}-{e['end_t']:g} s, "
                     f"peak score {e['peak_score']:.2f}; {e.get('top_proto')} from "
                     f"{e.get('top_src')} to {e.get('top_dst')}")
        for f in e.get("top_features", []):
            lines.append(f"  - {feature_name(f['feature'])}: {f['value']:g} (normal {f['normal']:g})")
    if state.get("routes"):
        lines += ["", "## Routes", ""]
        lines += [f"- t = {r['t']:.2f} s, flow {r['fid']}: {r['path']}" for r in state["routes"]]
    lines += ["", f"Windows analysed: {len(metrics)}", ""]
    return "\n".join(lines)


def compare_runs(a: dict, b: dict) -> pd.DataFrame:
    """Side-by-side headline numbers of two runs."""
    rows = [("Packets", "summary", "packets"), ("Duration (s)", "summary", "duration_s"),
            ("Hosts", "summary", "hosts"), ("Flows", "summary", "flows"),
            ("Latency / delay (ms)", "overall", "latency_ms"), ("Packet loss (%)", "overall", "loss_pct"),
            ("Jitter (ms)", "overall", "jitter_ms"), ("Throughput (Mb/s)", "overall", "throughput_mbps")]
    out = []
    for label, part, key in rows:
        out.append({"Measure": label, a["run"]["name"] + f" (#{a['run']['id']})": a.get(part, {}).get(key),
                    b["run"]["name"] + f" (#{b['run']['id']})": b.get(part, {}).get(key)})
    out.append({"Measure": "Incidents", a["run"]["name"] + f" (#{a['run']['id']})": len(a["incidents"]),
                b["run"]["name"] + f" (#{b['run']['id']})": len(b["incidents"])})
    return pd.DataFrame(out)


def simulate_link_failure(G: nx.Graph, link: tuple[str, str], source: str,
                          weight: str = "latency") -> pd.DataFrame:
    """Routing table of `source` before and after removing `link`, recomputed with
    Distance Vector (Bellman-Ford rounds). Rows whose next hop or cost changed are marked."""
    from netmind.topology import distance_vector_tables
    before, _ = distance_vector_tables(G, weight)
    H = G.copy()
    if H.has_edge(*link):
        H.remove_edge(*link)
    after, rounds = distance_vector_tables(H, weight)
    rows = []
    for dst in sorted(set(before.get(source, {})) | set(after.get(source, {}))):
        b, a = before[source].get(dst), after[source].get(dst)
        rows.append({"Destination": dst,
                     "Next hop before": b["next_hop"] if b else "-",
                     "Cost before": b["cost"] if b else None,
                     "Next hop after": a["next_hop"] if a else "unreachable",
                     "Cost after": a["cost"] if a else None,
                     "Changed": (b is None) != (a is None) or bool(b and a and (
                         b["next_hop"] != a["next_hop"] or abs(b["cost"] - a["cost"]) > 1e-9))})
    df = pd.DataFrame(rows)
    df.attrs["dv_rounds"] = rounds
    return df


def filter_flows(flows: pd.DataFrame, text: str = "", protocols: list[str] | None = None) -> pd.DataFrame:
    """Flows whose endpoints or flow id contain `text`, limited to the chosen protocols."""
    if flows is None or flows.empty:
        return flows
    out = flows
    if protocols:
        lbl = out["app"].where(out["app"].fillna("") != "", out["proto"]) if "app" in out else out["proto"]
        out = out[lbl.isin(protocols)]
    if text:
        t = text.strip().lower()
        hay = (out["flow"].astype(str) + " " + out.get("a", "").astype(str) + " "
               + out.get("b", "").astype(str)).str.lower()
        out = out[hay.str.contains(t, regex=False)]
    return out
