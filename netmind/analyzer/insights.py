"""Deeper traffic insights: TCP connection health, DNS, host inventory and a network health score.

    tcp_connections(df)       one row per TCP connection attempt and how it ended
    connection_summary(c)     counts, success rate, handshake time, likely scanners
    dns_summary(df)           queries, unanswered lookups, response time, top domains
    host_inventory(df, c)     per host: scope, role, services offered, traffic in/out, peers
    window_health(m, s, b)    0-100 health score per time window, with its penalties
    health_summary(h)         overall score, grade, worst window

All of these work on the common packet-record table (netmind/capture/records.py).
"""
from __future__ import annotations

import ipaddress

import numpy as np
import pandas as pd

SERVICE_NAMES = {20: "FTP data", 21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
                 80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 3306: "MySQL",
                 3389: "RDP", 8080: "HTTP alt"}
# A host is a likely scanner when at least this many of its connection attempts failed,
# to at least this many different destination ports.
SCAN_MIN_FAILED, SCAN_MIN_PORTS = 20, 20

CONN_COLUMNS = ["client", "cport", "server", "sport", "service", "start", "state", "handshake_ms",
                "closed", "packets", "bytes", "duration_s"]


def _key(a, ap, b, bp) -> pd.Series:
    """Builds a 'client:port>server:port' key to match packets of one connection."""
    return a.astype(str) + ":" + ap.astype(str) + ">" + b.astype(str) + ":" + bp.astype(str)


def tcp_connections(df: pd.DataFrame) -> pd.DataFrame:
    """Every TCP connection attempt (a SYN without ACK) and its outcome.

    state: established = the server answered SYN-ACK; refused = it answered RST;
    unanswered = no reply at all; reset = established, then aborted with RST.
    handshake_ms = SYN-ACK time - SYN time. closed = a FIN was seen.
    """
    if df.empty or "tcp_flags" not in df.columns:
        return pd.DataFrame(columns=CONN_COLUMNS)
    tcp = df[df["proto"] == "TCP"]
    if tcp.empty:
        return pd.DataFrame(columns=CONN_COLUMNS)
    flags = tcp["tcp_flags"].fillna("").astype(str)
    syn = tcp[flags.str.contains("S") & ~flags.str.contains("A")]
    if syn.empty:
        return pd.DataFrame(columns=CONN_COLUMNS)
    syn = syn.assign(key=_key(syn["src"], syn["sport"], syn["dst"], syn["dport"]))
    first = syn.groupby("key", sort=False).first()
    out_key = _key(tcp["src"], tcp["sport"], tcp["dst"], tcp["dport"])
    in_key = _key(tcp["dst"], tcp["dport"], tcp["src"], tcp["sport"])
    known = set(first.index)
    to_srv = tcp[out_key.isin(known)].assign(key=out_key[out_key.isin(known)])
    to_cli = tcp[in_key.isin(known)].assign(key=in_key[in_key.isin(known)])
    f_cli = to_cli["tcp_flags"].fillna("").astype(str)
    synack = to_cli[f_cli.str.contains("S") & f_cli.str.contains("A")].groupby("key")["ts"].min()
    both = pd.concat([to_srv, to_cli])
    f_both = both["tcp_flags"].fillna("").astype(str)
    rst = both[f_both.str.contains("R")].groupby("key")["ts"].min()
    fin = set(both[f_both.str.contains("F")]["key"])
    pk = both.groupby("key").agg(packets=("ts", "size"), bytes=("length", "sum"),
                                 t0=("ts", "min"), t1=("ts", "max"))
    c = first[["src", "sport", "dst", "dport", "ts"]].rename(
        columns={"src": "client", "sport": "cport", "dst": "server", "dport": "sport", "ts": "start"})
    c = c.join(pk)
    c["synack"] = synack.reindex(c.index)
    c["rst"] = rst.reindex(c.index)
    est = c["synack"].notna()
    state = np.where(est, "established", np.where(c["rst"].notna(), "refused", "unanswered"))
    state = np.where(est & c["rst"].notna() & (c["rst"] > c["synack"]), "reset", state)
    c["state"] = state
    c["handshake_ms"] = ((c["synack"] - c["start"]) * 1000).round(2)
    c["closed"] = c.index.isin(fin)
    c["duration_s"] = (c["t1"] - c["t0"]).round(3)
    c["service"] = c["sport"].map(lambda p: SERVICE_NAMES.get(int(p), f"port {int(p)}"))
    t_zero = df["ts"].min()
    c["start"] = (c["start"] - t_zero).round(3)
    return c.reset_index(drop=True)[CONN_COLUMNS].sort_values("start", kind="stable").reset_index(drop=True)


def connection_summary(conns: pd.DataFrame) -> dict:
    """Counts by outcome, success rate, handshake time and hosts whose attempts mostly failed."""
    n = int(len(conns))
    if n == 0:
        return {"attempts": 0}
    counts = conns["state"].value_counts()
    est = int(counts.get("established", 0)) + int(counts.get("reset", 0))
    failed = conns[conns["state"].isin(["refused", "unanswered"])]
    by_src = failed.groupby("client").agg(failed=("state", "size"), ports=("sport", "nunique"),
                                          targets=("server", "nunique")).reset_index()
    by_src = by_src.sort_values("failed", ascending=False)
    scanners = by_src[(by_src["failed"] >= SCAN_MIN_FAILED) & (by_src["ports"] >= SCAN_MIN_PORTS)]
    hs = conns["handshake_ms"].dropna()
    return {
        "attempts": n, "established": int(counts.get("established", 0)),
        "refused": int(counts.get("refused", 0)), "unanswered": int(counts.get("unanswered", 0)),
        "reset": int(counts.get("reset", 0)), "closed": int(conns["closed"].sum()),
        "success_pct": round(100 * est / n, 1),
        "handshake_ms_median": round(float(hs.median()), 2) if len(hs) else None,
        "handshake_ms_p95": round(float(hs.quantile(0.95)), 2) if len(hs) else None,
        "top_failing": by_src.head(5).to_dict("records"),
        "likely_scanners": scanners["client"].tolist(),
    }


def dns_summary(df: pd.DataFrame, top: int = 10) -> dict:
    """DNS lookups: how many, how many went unanswered, response time, most-queried names."""
    if df.empty or "dns_qr" not in df.columns:
        return {"queries": 0}
    q = df[df["dns_qr"] == 0]
    if q.empty:
        return {"queries": 0}
    r = df[df["dns_qr"] == 1]
    q = q.drop_duplicates(["src", "dns_id"], keep="first")
    rr = r.groupby(["dst", "dns_id"])["ts"].min().rename("rts")
    m = q.join(rr, on=["src", "dns_id"])
    m["response_ms"] = ((m["rts"] - m["ts"]) * 1000).where(m["rts"] >= m["ts"])
    names = m["dns_qname"].fillna("").astype(str).str.rstrip(".")
    m = m.assign(name=names.where(names != "", "(unknown)"))
    doms = m.groupby("name").agg(queries=("ts", "size"), unanswered=("response_ms", lambda s: int(s.isna().sum())),
                                 response_ms=("response_ms", "median")).reset_index()
    doms["response_ms"] = doms["response_ms"].round(2)
    doms = doms.sort_values(["queries", "name"], ascending=[False, True]).head(top)
    resp = m["response_ms"].dropna()
    return {
        "queries": int(len(m)), "answered": int(m["response_ms"].notna().sum()),
        "unanswered": int(m["response_ms"].isna().sum()),
        "response_ms_median": round(float(resp.median()), 2) if len(resp) else None,
        "response_ms_p95": round(float(resp.quantile(0.95)), 2) if len(resp) else None,
        "clients": int(m["src"].nunique()), "servers": int(r["src"].nunique()),
        "top_domains": doms.where(doms.notna(), None).to_dict("records"),
    }


def ip_scope(addr: str) -> str:
    """private / public / loopback / multicast / link-local, or 'simulated' for NS2 node names."""
    try:
        ip = ipaddress.ip_address(str(addr))
    except ValueError:
        return "simulated"
    if ip.is_loopback:
        return "loopback"
    if ip.is_multicast:
        return "multicast"
    if ip.is_link_local:
        return "link-local"
    return "private" if ip.is_private else "public"


def host_inventory(df: pd.DataFrame, conns: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per host: scope, role, services it answered on, traffic sent/received, peers."""
    cols = ["host", "scope", "role", "services", "packets_out", "bytes_out", "packets_in",
            "bytes_in", "peers", "first_seen", "last_seen"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    t0 = df["ts"].min()
    out = df.groupby("src").agg(packets_out=("ts", "size"), bytes_out=("length", "sum"),
                                first_out=("ts", "min"), last_out=("ts", "max"))
    inn = df.groupby("dst").agg(packets_in=("ts", "size"), bytes_in=("length", "sum"),
                                first_in=("ts", "min"), last_in=("ts", "max"))
    h = out.join(inn, how="outer")
    pairs = pd.concat([df[["src", "dst"]].rename(columns={"src": "a", "dst": "b"}),
                       df[["dst", "src"]].rename(columns={"dst": "a", "src": "b"})])
    h["peers"] = pairs.drop_duplicates().groupby("a").size()
    services: dict[str, set] = {}
    initiated: set = set()
    if conns is not None and not conns.empty:
        ok = conns[conns["state"].isin(["established", "reset"])]
        for srv, port, name in zip(ok["server"], ok["sport"], ok["service"]):
            services.setdefault(srv, set()).add(f"TCP {int(port)} ({name})" if not name.startswith("port")
                                                else f"TCP {int(port)}")
        initiated |= set(conns["client"])
    if "dns_qr" in df.columns:
        for s in df.loc[df["dns_qr"] == 1, "src"].unique():
            services.setdefault(s, set()).add("DNS 53")
        initiated |= set(df.loc[df["dns_qr"] == 0, "src"])
    if "icmp_type" in df.columns:
        for s in df.loc[df["icmp_type"] == 0, "src"].unique():
            services.setdefault(s, set()).add("ICMP echo")
        initiated |= set(df.loc[df["icmp_type"] == 8, "src"])
    scanners = set(connection_summary(conns).get("likely_scanners", [])) if conns is not None else set()
    rows = []
    for host, r in h.iterrows():
        svc = sorted(services.get(host, set()))
        if host in scanners:
            role = "likely scanner"
        elif svc and host in initiated:
            role = "client + server"
        elif svc:
            role = "server"
        elif host in initiated:
            role = "client"
        elif r.get("packets_out", 0) > 0 and not r.get("packets_in", 0) > 0:
            role = "sender"
        elif r.get("packets_in", 0) > 0 and not r.get("packets_out", 0) > 0:
            role = "receiver"
        else:
            role = "other"
        first = np.nanmin([r.get("first_out", np.nan), r.get("first_in", np.nan)])
        last = np.nanmax([r.get("last_out", np.nan), r.get("last_in", np.nan)])
        rows.append({"host": host, "scope": ip_scope(host), "role": role, "services": ", ".join(svc),
                     "packets_out": int(np.nan_to_num(r.get("packets_out", 0))),
                     "bytes_out": int(np.nan_to_num(r.get("bytes_out", 0))),
                     "packets_in": int(np.nan_to_num(r.get("packets_in", 0))),
                     "bytes_in": int(np.nan_to_num(r.get("bytes_in", 0))),
                     "peers": int(np.nan_to_num(r.get("peers", 0))),
                     "first_seen": round(float(first - t0), 3), "last_seen": round(float(last - t0), 3)})
    inv = pd.DataFrame(rows, columns=cols)
    inv["total"] = inv["bytes_out"] + inv["bytes_in"]
    return inv.sort_values("total", ascending=False).drop(columns="total").reset_index(drop=True)


# ---------------------------------------------------------------------------
# health score
# ---------------------------------------------------------------------------
# Penalties (points out of 100), each saturating:
#   latency: up to 40 when latency reaches 4x the normal level (linear from 1x)
#   loss:    up to 40 when loss reaches 5%
#   anomaly: 20 when the detector flagged the window
LAT_MAX, LAT_FULL_RATIO = 40.0, 4.0
LOSS_MAX, LOSS_FULL_PCT = 40.0, 5.0
ANOM_MAX = 20.0


def window_health(metrics: pd.DataFrame, scores: pd.DataFrame | None, baseline: dict) -> pd.DataFrame:
    """0-100 score per window: 100 minus latency, loss and anomaly penalties."""
    out = pd.DataFrame({"t": metrics["t"]}) if "t" in metrics.columns else pd.DataFrame(index=metrics.index)
    lat = metrics["latency_ms"] if "latency_ms" in metrics.columns else pd.Series(np.nan, index=metrics.index)
    base = baseline.get("latency_ms") if baseline else None
    if base is None or not np.isfinite(base) or base <= 0:
        med = lat.dropna()
        base = float(med.median()) if len(med) else None
    if base:
        ratio = (lat / base).fillna(1.0)
        out["lat_penalty"] = (LAT_MAX * ((ratio - 1) / (LAT_FULL_RATIO - 1)).clip(0, 1)).round(1)
    else:
        out["lat_penalty"] = 0.0
    loss = metrics["loss_pct"].fillna(0) if "loss_pct" in metrics.columns else pd.Series(0.0, index=metrics.index)
    out["loss_penalty"] = (LOSS_MAX * (loss / LOSS_FULL_PCT).clip(0, 1)).round(1)
    flagged = pd.Series(False, index=metrics.index)
    if scores is not None and "is_anomaly" in scores.columns and len(scores) == len(metrics):
        flagged = scores["is_anomaly"].fillna(False).astype(bool).values
    out["anomaly_penalty"] = np.where(flagged, ANOM_MAX, 0.0)
    out["health"] = (100 - out["lat_penalty"] - out["loss_penalty"] - out["anomaly_penalty"]).clip(0, 100).round(1)
    return out


def grade(score: float | None) -> str:
    """Turns a health score into Good (90+), Fair (70-90) or Poor."""
    if score is None:
        return "n/a"
    return "Good" if score >= 90 else "Fair" if score >= 70 else "Poor"


def health_summary(h: pd.DataFrame) -> dict:
    """The run's average health, its grade and the worst window."""
    if h.empty:
        return {"score": None, "grade": "n/a"}
    score = round(float(h["health"].mean()), 1)
    worst = h.loc[h["health"].idxmin()]
    return {"score": score, "grade": grade(score), "worst": round(float(worst["health"]), 1),
            "worst_t": round(float(worst["t"]), 3) if "t" in h.columns else None,
            "poor_windows": int((h["health"] < 70).sum()), "windows": int(len(h)),
            "penalty_points": {"latency": round(float(h["lat_penalty"].mean()), 1),
                               "loss": round(float(h["loss_penalty"].mean()), 1),
                               "anomaly": round(float(h["anomaly_penalty"].mean()), 1)}}
