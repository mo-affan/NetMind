#!/usr/bin/env python3
"""
NetMind - quick NS2 trace check using ONLY the Python standard library.

For lab machines that have NS2 and python3 but no pandas/numpy/scikit-learn. It uses the
same definitions as netmind/capture/ns2.py, so its numbers match the full analysis:

  sent       a data packet's first "+" at its source node
  delivered  "r" at its destination node;  dropped: a "d" event (and never delivered)
  loss %     dropped / (delivered + dropped), by the window the packet was SENT in
  delay      one-way: delivered time - sent time (ms), by send window
  throughput bytes delivered in the window x 8 / window (Mb/s), by delivery window

Usage:
  python3 check_trace.py netmind.tr
  python3 check_trace.py netmind.tr --window 0.5
Exit code 0 = the scenario's expected behaviour was found, 1 = something is missing.
"""
import argparse
import sys
from collections import defaultdict

DATA = {"tcp", "cbr", "udp", "exp", "pareto", "ftp", "telnet"}


def node(a):
    """Node number from an NS2 address."""
    return int(a.split(".")[0])


def load(path):
    """Reads the trace: packet events, link up/down lines, other lines."""
    events, link_lines, other = [], [], defaultdict(int)
    with open(path, errors="replace") as f:
        for line in f:
            p = line.split()
            if not p:
                continue
            if "link-down" in line or "link-up" in line:
                link_lines.append(line.strip())
                continue
            if len(p) < 12 or p[0] not in "+-rd" or len(p[0]) != 1:
                other[p[0]] += 1
                continue
            try:
                events.append((p[0], float(p[1]), int(p[2]), int(p[3]), p[4], int(p[5]),
                               int(p[7]), node(p[8]), node(p[9]), int(p[10]), int(p[11])))
            except ValueError:
                other["malformed"] += 1
    return events, link_lines, other


def analyse(events):
    """Follows every data packet: send, receive or drop time and its hops."""
    pk = {}
    hops = defaultdict(list)
    for ev, t, frm, to, typ, size, fid, src, dst, seq, pid in sorted(events, key=lambda e: e[1]):
        if typ not in DATA:
            continue
        if ev == "+" and frm == src and pid not in pk:
            pk[pid] = {"t": t, "fid": fid, "type": typ, "size": size, "src": src, "dst": dst,
                       "seq": seq, "recv": None, "drop": None, "drop_link": None}
        elif pid in pk:
            if ev == "r":
                hops[pid].append(to)
                if to == dst and pk[pid]["recv"] is None:
                    pk[pid]["recv"] = t
            elif ev == "d" and pk[pid]["drop"] is None:
                pk[pid]["drop"] = t
                pk[pid]["drop_link"] = f"n{min(frm, to)}-n{max(frm, to)}"
    return pk, hops


def routes(pk, hops):
    """Route of each flow over time: a new entry each time a delivered packet took a new path."""
    out, last = [], {}
    for pid, p in sorted(pk.items(), key=lambda kv: kv[1]["t"]):
        if p["recv"] is None:
            continue
        path = "-".join(f"n{x}" for x in [p["src"]] + hops[pid])
        if last.get(p["fid"]) != path:
            out.append({"t": p["t"], "fid": p["fid"], "path": path})
            last[p["fid"]] = path
    return out


def scenario_checks(pk, hops):
    """The five expected behaviours of netmind_scenario.tcl: [(name, passed)], and the numbers."""
    def window_stats(t0, t1, fid=None):
        """Drops and mean delay of packets sent in a time range."""
        sel = [p for p in pk.values() if t0 <= p["t"] < t1 and (fid is None or p["fid"] == fid)]
        got = [p for p in sel if p["recv"] is not None]
        drop = [p for p in sel if p["recv"] is None and p["drop"] is not None]
        delay = sum((p["recv"] - p["t"]) for p in got) / len(got) * 1000 if got else 0
        return len(drop), delay

    d_norm, delay_norm = window_stats(0.5, 3.0)
    d_cong, delay_cong = window_stats(3.0, 6.0)
    _, delay_fail = window_stats(7.1, 8.4, fid=1)
    rerouted = any("n4" in "-".join(f"n{x}" for x in hops[pid]) and 7.0 <= p["t"] < 8.5
                   for pid, p in pk.items() if p["recv"] is not None)
    checks = [
        ("no drops before the UDP burst (0.5-3 s)", d_norm == 0),
        ("drops during the UDP burst (3-6 s)", d_cong > 0),
        ("delay higher during the burst than before", delay_cong > 1.3 * delay_norm > 0),
        ("traffic rerouted via n4 during the link failure (7-8.5 s)", rerouted),
        ("TCP delay higher on the backup path", delay_fail > 1.3 * delay_norm > 0),
    ]
    stats = {"delay_normal_ms": delay_norm, "delay_burst_ms": delay_cong, "delay_failure_ms": delay_fail,
             "drops_normal": d_norm, "drops_burst": d_cong, "rerouted": rerouted}
    return checks, stats


def main():
    """Prints the per-flow, per-window, routes and scenario-check report."""
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--window", type=float, default=1.0)
    a = ap.parse_args()
    events, link_lines, other = load(a.trace)
    if not events:
        print(f"No packet events found in {a.trace}. Is this the file written by `$ns trace-all`?")
        return 1
    types = defaultdict(int)
    for e in events:
        types[(e[0], e[4])] += 1
    pk, hops = analyse(events)
    t_end = max(e[1] for e in events)
    print(f"Trace: {a.trace}  ({len(events)} packet events, last event at t={t_end:.3f} s)")
    print("Event counts:", ", ".join(f"{ev} {typ}: {n}" for (ev, typ), n in sorted(types.items())))
    if other:
        print("Skipped lines:", dict(other))

    # ---- per flow ----
    print("\nPer flow")
    print(f"{'fid':>3} {'type':<5} {'path':<8} {'sent':>6} {'deliv':>6} {'drop':>5} {'loss%':>6} "
          f"{'retx':>5} {'avg delay ms':>13}")
    flows = defaultdict(list)
    for p in pk.values():
        flows[p["fid"]].append(p)
    for fid in sorted(flows):
        ps = sorted(flows[fid], key=lambda p: p["t"])
        got = [p for p in ps if p["recv"] is not None]
        drop = [p for p in ps if p["recv"] is None and p["drop"] is not None]
        seen, retx = set(), 0
        for p in ps:
            if p["type"] == "tcp" and p["seq"] in seen:
                retx += 1
            seen.add(p["seq"])
        loss = 100 * len(drop) / (len(got) + len(drop)) if got or drop else 0
        delay = sum((p["recv"] - p["t"]) * 1000 for p in got) / len(got) if got else float("nan")
        print(f"{fid:>3} {ps[0]['type']:<5} n{ps[0]['src']}->n{ps[0]['dst']:<3} {len(ps):>6} {len(got):>6} "
              f"{len(drop):>5} {loss:>6.2f} {retx:>5} {delay:>13.2f}")

    # ---- per window ----
    w = a.window
    rows = defaultdict(lambda: {"sent": 0, "got": 0, "drop": 0, "delay": [], "bytes": 0})
    for p in pk.values():
        r = rows[int(p["t"] // w)]
        r["sent"] += 1
        if p["recv"] is not None:
            r["got"] += 1
            r["delay"].append((p["recv"] - p["t"]) * 1000)
            rows[int(p["recv"] // w)]["bytes"] += p["size"]
        elif p["drop"] is not None:
            r["drop"] += 1
    print(f"\nPer {w:g} s window (by send time; throughput by delivery time)")
    print(f"{'t':>6} {'sent':>5} {'drop':>5} {'loss%':>6} {'delay ms':>9} {'Mb/s':>7}")
    for k in range(int(t_end // w) + 1):
        r = rows[k]
        known = r["got"] + r["drop"]
        d = sum(r["delay"]) / len(r["delay"]) if r["delay"] else float("nan")
        print(f"{k * w:>6.2f} {r['sent']:>5} {r['drop']:>5} {100 * r['drop'] / known if known else 0:>6.2f} "
              f"{d:>9.2f} {r['bytes'] * 8 / w / 1e6:>7.3f}")

    # ---- drops per link ----
    per_link = defaultdict(int)
    for p in pk.values():
        if p["recv"] is None and p["drop"] is not None:
            per_link[p["drop_link"]] += 1
    print("\nDropped data packets per link:", dict(per_link) or "none")

    # ---- routes ----
    print("\nRoutes (new line = route changed):")
    for r in routes(pk, hops):
        print(f"  t={r['t']:7.3f} s  flow {r['fid']}: {r['path']}")
    if link_lines:
        print("\nLink status lines in the trace:")
        for l in link_lines[:10]:
            print("  " + l)

    # ---- scenario checks (netmind_scenario.tcl) ----
    checks, st = scenario_checks(pk, hops)
    print("\nScenario checks")
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"  (delay before burst {st['delay_normal_ms']:.1f} ms, during burst {st['delay_burst_ms']:.1f} ms, "
          f"TCP during failure {st['delay_failure_ms']:.1f} ms; drops before {st['drops_normal']}, "
          f"during {st['drops_burst']})")
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
