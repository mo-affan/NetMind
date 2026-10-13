"""M4 Performance Analyzer: latency, throughput, packet loss, jitter, traffic rate, utilization.

How each metric is obtained from captured packets:

* Latency (RTT): time between a request and its reply, from three kinds of pairs:
  TCP SYN -> SYN-ACK, ICMP echo request -> echo reply, DNS query -> DNS response.
* Throughput: bytes x 8 / window length, in Mbps.
* Packet loss: a passive capture cannot see packets that never arrived, so loss is
  estimated from TCP retransmissions (the same data segment sent again) and from
  ICMP echo requests that never got a reply.
* Jitter: mean absolute difference between consecutive RTT samples on the same path.
* Traffic rate: packets per second. Utilization: throughput / link capacity.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# RTT samples
# ---------------------------------------------------------------------------
def rtt_samples(df: pd.DataFrame) -> pd.DataFrame:
    """Every RTT measurement found in the capture: ts, rtt_ms, kind, client, server."""
    cols = ["ts", "rtt_ms", "kind", "client", "server"]
    parts = []

    tcp = df[df["proto"] == "TCP"]
    syn = tcp[tcp["tcp_flags"] == "S"][["ts", "src", "dst", "sport", "dport", "seq"]]
    sa = tcp[tcp["tcp_flags"] == "SA"][["ts", "src", "dst", "sport", "dport", "ack"]]
    if not syn.empty and not sa.empty:
        syn = syn.assign(exp_ack=(syn["seq"] + 1) % 2**32)
        m = syn.merge(sa, left_on=["src", "dst", "sport", "dport", "exp_ack"],
                      right_on=["dst", "src", "dport", "sport", "ack"], suffixes=("", "_r"))
        m = m[m["ts_r"] >= m["ts"]]
        parts.append(pd.DataFrame({"ts": m["ts"], "rtt_ms": (m["ts_r"] - m["ts"]) * 1000,
                                   "kind": "tcp_handshake", "client": m["src"], "server": m["dst"]}))

    icmp = df[df["proto"] == "ICMP"]
    req = icmp[icmp["icmp_type"] == 8][["ts", "src", "dst", "icmp_id", "icmp_seq"]]
    rep = icmp[icmp["icmp_type"] == 0][["ts", "src", "dst", "icmp_id", "icmp_seq"]]
    if not req.empty and not rep.empty:
        m = req.merge(rep, left_on=["src", "dst", "icmp_id", "icmp_seq"],
                      right_on=["dst", "src", "icmp_id", "icmp_seq"], suffixes=("", "_r"))
        m = m[m["ts_r"] >= m["ts"]]
        parts.append(pd.DataFrame({"ts": m["ts"], "rtt_ms": (m["ts_r"] - m["ts"]) * 1000,
                                   "kind": "icmp_echo", "client": m["src"], "server": m["dst"]}))

    dns = df[df["dns_id"] >= 0]
    q = dns[dns["dns_qr"] == 0][["ts", "src", "dst", "sport", "dns_id"]]
    a = dns[dns["dns_qr"] == 1][["ts", "src", "dst", "dport", "dns_id"]]
    if not q.empty and not a.empty:
        m = q.merge(a, left_on=["src", "dst", "sport", "dns_id"],
                    right_on=["dst", "src", "dport", "dns_id"], suffixes=("", "_r"))
        m = m[m["ts_r"] >= m["ts"]]
        parts.append(pd.DataFrame({"ts": m["ts"], "rtt_ms": (m["ts_r"] - m["ts"]) * 1000,
                                   "kind": "dns", "client": m["src"], "server": m["dst"]}))

    if not parts:
        return pd.DataFrame(columns=cols)
    out = pd.concat(parts, ignore_index=True)
    # one sample per request: keep the first reply
    out = out.sort_values(["ts", "rtt_ms"]).drop_duplicates(["ts", "client", "server", "kind"])
    return out[cols].sort_values("ts").reset_index(drop=True)


def jitter_ms(rtts: pd.Series | np.ndarray) -> float:
    """Mean absolute difference between consecutive RTT samples of one path."""
    v = np.asarray(rtts, dtype=float)
    return float(np.mean(np.abs(np.diff(v)))) if v.size > 1 else 0.0


def path_latency(rtt: pd.DataFrame) -> tuple[float, float]:
    """(latency_ms, jitter_ms) for a set of RTT samples.

    Samples are grouped by path (client, server, kind) first, because a 3 ms ping to the
    gateway and a 45 ms handshake to a web server are different paths: mixing them would
    make jitter look huge. Latency is the mean of the per-path means; jitter is the mean
    of the per-path jitters. Every path counts equally, so a flood of pings to one host
    cannot hide a slow web server.
    """
    if rtt.empty:
        return float("nan"), 0.0
    g = rtt.sort_values("ts").groupby(["client", "server", "kind"])["rtt_ms"]
    means = g.mean()
    jit = g.apply(jitter_ms)[g.size() > 1]
    return float(means.mean()), float(jit.mean()) if len(jit) else 0.0


# ---------------------------------------------------------------------------
# Loss
# ---------------------------------------------------------------------------
def retransmissions(df: pd.DataFrame) -> pd.DataFrame:
    """TCP data segments seen more than once (same direction, ports and sequence number)."""
    data = df[(df["proto"] == "TCP") & (df["payload_len"] > 0)]
    key = ["src", "dst", "sport", "dport", "seq"]
    dup = data.duplicated(subset=key, keep="first")
    return data[dup]


def icmp_unanswered(df: pd.DataFrame) -> tuple[int, int]:
    """(echo requests, requests that never got a reply)."""
    icmp = df[df["proto"] == "ICMP"]
    req = icmp[icmp["icmp_type"] == 8]
    rep = icmp[icmp["icmp_type"] == 0]
    if req.empty:
        return 0, 0
    answered = req.merge(rep, left_on=["src", "dst", "icmp_id", "icmp_seq"],
                         right_on=["dst", "src", "icmp_id", "icmp_seq"], how="inner")
    answered = answered.drop_duplicates(["src_x", "dst_x", "icmp_id", "icmp_seq"])
    return int(len(req)), int(len(req) - len(answered))


# ---------------------------------------------------------------------------
# Per-window metrics
# ---------------------------------------------------------------------------
def window_metrics(df: pd.DataFrame, window: float = 5.0,
                   link_capacity_mbps: float = 100.0) -> pd.DataFrame:
    """Performance metrics for every `window`-second slice of the capture."""
    cols = ["window_start", "t", "packets", "bytes", "pps", "throughput_mbps", "utilization_pct",
            "latency_ms", "jitter_ms", "rtt_samples", "retransmissions", "data_segments",
            "tcp_loss_pct", "icmp_loss_pct", "loss_pct", "connections"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    t0 = df["ts"].min()
    w = ((df["ts"] - t0) // window).astype(int)
    rtt = rtt_samples(df)
    rtt_w = ((rtt["ts"] - t0) // window).astype(int) if not rtt.empty else pd.Series(dtype=int)
    retx = retransmissions(df)
    retx_w = ((retx["ts"] - t0) // window).astype(int)
    data = df[(df["proto"] == "TCP") & (df["payload_len"] > 0)]
    data_w = ((data["ts"] - t0) // window).astype(int)

    rows = []
    for k in range(int(w.max()) + 1):
        part = df[w == k]
        r = rtt[rtt_w == k] if not rtt.empty else rtt
        lat, jit = path_latency(r)
        nbytes = int(part["length"].sum())
        n_data = int((data_w == k).sum())
        n_retx = int((retx_w == k).sum())
        req, lost = icmp_unanswered(part)
        tcp_loss = 100 * n_retx / n_data if n_data else 0.0
        icmp_loss = 100 * lost / req if req else 0.0
        # combined estimate: weight each by how many packets it is based on
        loss = (100 * (n_retx + lost) / (n_data + req)) if (n_data + req) else 0.0
        thr = nbytes * 8 / window / 1e6
        rows.append({
            "window_start": round(float(t0 + k * window), 3),
            "t": round(k * window, 3),
            "packets": int(len(part)), "bytes": nbytes,
            "pps": round(len(part) / window, 2),
            "throughput_mbps": round(thr, 4),
            "utilization_pct": round(100 * thr / link_capacity_mbps, 3),
            "latency_ms": round(lat, 2) if len(r) else np.nan,
            "jitter_ms": round(jit, 2),
            "rtt_samples": int(len(r)),
            "retransmissions": n_retx, "data_segments": n_data,
            "tcp_loss_pct": round(tcp_loss, 2), "icmp_loss_pct": round(icmp_loss, 2),
            "loss_pct": round(loss, 2),
            "connections": int(((part["proto"] == "TCP") & (part["tcp_flags"] == "S")).sum()),
        })
    return pd.DataFrame(rows, columns=cols)


def overall(df: pd.DataFrame, link_capacity_mbps: float = 100.0) -> dict:
    """Whole-capture numbers for the dashboard's headline tiles."""
    if df.empty:
        return {}
    dur = max(float(df["ts"].max() - df["ts"].min()), 1e-9)
    rtt = rtt_samples(df)
    retx = retransmissions(df)
    n_data = int(((df["proto"] == "TCP") & (df["payload_len"] > 0)).sum())
    req, lost = icmp_unanswered(df)
    thr = df["length"].sum() * 8 / dur / 1e6
    lat, jit = path_latency(rtt)
    return {
        "duration_s": round(dur, 2),
        "latency_ms": round(lat, 2) if not rtt.empty else None,
        "latency_p95_ms": round(float(rtt["rtt_ms"].quantile(0.95)), 2) if not rtt.empty else None,
        "jitter_ms": round(jit, 2) if not rtt.empty else None,
        "throughput_mbps": round(float(thr), 4),
        "utilization_pct": round(float(100 * thr / link_capacity_mbps), 3),
        "pps": round(len(df) / dur, 2),
        "retransmissions": int(len(retx)),
        "tcp_loss_pct": round(100 * len(retx) / n_data, 2) if n_data else 0.0,
        "icmp_loss_pct": round(100 * lost / req, 2) if req else 0.0,
        "loss_pct": round(100 * (len(retx) + lost) / (n_data + req), 2) if (n_data + req) else 0.0,
    }
