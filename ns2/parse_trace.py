"""
NetMind - NS2 trace parser

Reads an NS2 wired trace file (netmind.tr) and calculates, for every flow and
every time window, the same metrics NetMind calculates from live traffic:
throughput, packet loss, average delay (latency) and jitter.

NS2 trace line format (wired):
  event time from to type size flags fid src dst seq pktid
  event: + enqueue   - dequeue   r receive   d drop
  src / dst look like "0.0" = node.port

Usage:
  python parse_trace.py netmind.tr               # print table, write netmind_metrics.csv
  python parse_trace.py netmind.tr --window 0.5  # change window size (seconds)
"""
import argparse
import csv
from collections import defaultdict

DATA_TYPES = {"tcp", "cbr"}          # ignore ACKs and routing packets (rtProtoDV)
FLOW_NAMES = {1: "TCP (FTP)", 2: "UDP (CBR)"}


def parse(path):
    events = []
    with open(path) as f:
        for line in f:
            p = line.split()
            if len(p) < 12 or p[0] not in "+-rd":
                continue
            if p[4] not in DATA_TYPES:
                continue
            events.append({
                "ev": p[0], "t": float(p[1]), "frm": int(p[2]), "to": int(p[3]),
                "size": int(p[5]), "fid": int(p[7]),
                "src": int(p[8].split(".")[0]), "dst": int(p[9].split(".")[0]),
                "pkt": int(p[11]),
            })
    return events


def metrics(events, window):
    sent = {}          # pktid -> time it first left its source node
    recv = {}          # pktid -> time it reached its destination node
    dropped = set()
    meta = {}          # pktid -> (fid, size)
    for e in events:
        meta[e["pkt"]] = (e["fid"], e["size"])
        if e["ev"] == "+" and e["frm"] == e["src"] and e["pkt"] not in sent:
            sent[e["pkt"]] = e["t"]
        elif e["ev"] == "r" and e["to"] == e["dst"]:
            recv[e["pkt"]] = e["t"]
        elif e["ev"] == "d":
            dropped.add(e["pkt"])

    rows = defaultdict(lambda: {"sent": 0, "recv": 0, "drop": 0, "bytes": 0, "delays": []})
    for pkt, t0 in sent.items():
        fid, size = meta[pkt]
        w = int(t0 // window)
        r = rows[(fid, w)]
        r["sent"] += 1
        if pkt in recv:
            r["recv"] += 1
            r["delays"].append((t0, recv[pkt] - t0))
        if pkt in dropped and pkt not in recv:
            r["drop"] += 1
    for pkt, t1 in recv.items():
        fid, size = meta[pkt]
        rows[(fid, int(t1 // window))]["bytes"] += size

    out = []
    for (fid, w), r in sorted(rows.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        d = [x[1] for x in sorted(r["delays"])]
        avg = sum(d) / len(d) * 1000 if d else 0.0
        jit = (sum(abs(d[i] - d[i - 1]) for i in range(1, len(d))) / (len(d) - 1) * 1000
               if len(d) > 1 else 0.0)
        out.append({
            "window_start_s": round(w * window, 2),
            "flow": FLOW_NAMES.get(fid, f"flow {fid}"),
            "packets_sent": r["sent"],
            "packets_dropped": r["drop"],
            "loss_pct": round(100 * r["drop"] / r["sent"], 1) if r["sent"] else 0.0,
            "throughput_mbps": round(r["bytes"] * 8 / window / 1e6, 3),
            "avg_delay_ms": round(avg, 1),
            "jitter_ms": round(jit, 1),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--window", type=float, default=1.0)
    ap.add_argument("--out", default="netmind_metrics.csv")
    a = ap.parse_args()

    rows = metrics(parse(a.trace), a.window)
    if not rows:
        print("No data packets found in the trace.")
        return
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    print(f"{'time(s)':>7}  {'flow':<10} {'sent':>5} {'drop':>5} {'loss%':>6} "
          f"{'Mbps':>6} {'delay ms':>9} {'jitter ms':>9}")
    for r in rows:
        print(f"{r['window_start_s']:>7}  {r['flow']:<10} {r['packets_sent']:>5} "
              f"{r['packets_dropped']:>5} {r['loss_pct']:>6} {r['throughput_mbps']:>6} "
              f"{r['avg_delay_ms']:>9} {r['jitter_ms']:>9}")
    print(f"\nSaved {len(rows)} rows to {a.out}")


if __name__ == "__main__":
    main()
