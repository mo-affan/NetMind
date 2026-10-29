"""Group anomalous windows into incidents and label what kind of problem each looks like.

Consecutive anomalous windows (allowing a one-window gap) become one episode. For each
episode we record when it happened, its peak score, the features that stood out, the
busiest source/destination/protocol in that period, and a likely type:

  port_scan   many distinct destination ports / connections, small packets
  flood       packet rate far above normal with small packets (e.g. ping flood)
  congestion  latency, loss or retransmissions far above normal
  traffic_spike  traffic volume far above normal (large transfer)
  reroute     (NS2) a flow changed path during the episode, i.e. a link failed
  unusual     none of the above patterns
"""
from __future__ import annotations

import json

import pandas as pd

TYPES = {
    "port_scan": "Possible port scan",
    "flood": "Traffic flood",
    "congestion": "Network congestion",
    "traffic_spike": "Traffic spike",
    "reroute": "Link failure and rerouting",
    "unusual": "Unusual traffic",
}


def classify(top: list[dict]) -> str:
    """Names an incident from its strongest features: scan, congestion, flood, spike."""
    z = {f["feature"]: f["z"] for f in top}
    perf = max((z.get(f, 0) for f in ("latency_ms", "loss_pct", "retransmissions")), default=0)
    small_pkts = "avg_pkt_size" in z and z["avg_pkt_size"] <= 0
    if z.get("dst_ports", 0) >= 6 or (z.get("connections", 0) >= 10 and small_pkts):
        return "port_scan"
    if perf >= 6:
        return "congestion"
    if z.get("pps", 0) >= 6 and small_pkts:
        return "flood"
    if perf >= 3:
        return "congestion"
    if z.get("bytes_per_sec", 0) >= 6 or z.get("pps", 0) >= 6 or z.get("throughput_mbps", 0) >= 6:
        return "traffic_spike"
    return "unusual"


def episodes(scores: pd.DataFrame, df: pd.DataFrame | None = None, window: float = 2.0,
             gap: int = 1) -> pd.DataFrame:
    """Merge anomalous windows into episodes. `df` (packet records) adds top source/dest/protocol."""
    cols = ["start_t", "end_t", "windows", "peak_score", "peak_deviation", "type", "title",
            "top_features", "top_src", "top_dst", "top_proto", "pps", "start_ts", "end_ts"]
    a = scores[scores["is_anomaly"]].sort_values("t")
    if a.empty:
        return pd.DataFrame(columns=cols)
    groups, cur = [], [a.iloc[0]]
    for _, row in a.iloc[1:].iterrows():
        if row["t"] - cur[-1]["t"] <= window * (gap + 1) + 1e-9:
            cur.append(row)
        else:
            groups.append(cur)
            cur = [row]
    groups.append(cur)

    t0 = df["ts"].min() if df is not None and not df.empty else 0.0
    rows = []
    for g in groups:
        gdf = pd.DataFrame(g)
        peak = gdf.loc[gdf["max_deviation"].idxmax()] if "max_deviation" in gdf else gdf.iloc[0]
        top = json.loads(peak["top_features"]) if isinstance(peak["top_features"], str) \
            else peak["top_features"]
        # strongest deviation per feature across the episode
        best: dict[str, dict] = {}
        for tf in gdf["top_features"]:
            for f in (json.loads(tf) if isinstance(tf, str) else tf):
                if f["feature"] not in best or abs(f["z"]) > abs(best[f["feature"]]["z"]):
                    best[f["feature"]] = f
        merged = sorted(best.values(), key=lambda f: -abs(f["z"]))[:4] or top
        kind = classify(merged)
        start_t, end_t = float(gdf["t"].min()), float(gdf["t"].max()) + window
        row = {"start_t": start_t, "end_t": end_t, "windows": len(gdf),
               "peak_score": float(gdf["anomaly_score"].max()),
               "peak_deviation": float(gdf.get("max_deviation", pd.Series([0])).max()),
               "type": kind, "title": TYPES[kind], "top_features": json.dumps(merged),
               "top_src": "", "top_dst": "", "top_proto": "", "pps": 0.0,
               "start_ts": t0 + start_t, "end_ts": t0 + end_t}
        if df is not None and not df.empty:
            part = df[(df["ts"] >= t0 + start_t) & (df["ts"] < t0 + end_t)]
            if not part.empty:
                lbl = part["app"].where(part["app"] != "", part["proto"])
                # who started it: count requests (SYN, ping, DNS query), not the replies
                req = part[(part["tcp_flags"] == "S") | (part["icmp_type"] == 8) | (part["dns_qr"] == 0)]
                who = req if len(req) >= 0.2 * len(part) else part
                row.update(top_src=who["src"].mode().iat[0], top_dst=who["dst"].mode().iat[0],
                           top_proto=lbl.mode().iat[0],
                           pps=round(len(part) / max(end_t - start_t, 1e-9), 1))
        rows.append(row)
    return pd.DataFrame(rows, columns=cols)
