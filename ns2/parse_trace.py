"""
NetMind - NS2 trace parser (command line)

Reads an NS2 wired trace file and prints, for every time window, the metrics
NetMind calculates: packets sent, dropped, loss %, throughput, one-way delay and
jitter. Also prints when a flow's route changed (rerouting after a link failure).

Usage (from the repo root or this folder):
  python ns2/parse_trace.py ns2/netmind.tr
  python ns2/parse_trace.py ns2/netmind.tr --window 0.5 --per-flow
  python -m netmind ns2 ns2/netmind.tr        # full pipeline: saves to the database too
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for `netmind`

from netmind.capture.ns2 import read_trace, trace_metrics, path_changes, trace_links  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--window", type=float, default=1.0)
    ap.add_argument("--per-flow", action="store_true")
    ap.add_argument("--out", default="netmind_metrics.csv")
    a = ap.parse_args()

    ev = read_trace(a.trace)
    if ev.empty:
        print("No events found. Is this an NS2 wired trace (trace-all)?")
        return
    m = trace_metrics(ev, a.window, per_flow=a.per_flow)
    m.to_csv(a.out, index=False)
    print(m.to_string(index=False))
    print(f"\nSaved {len(m)} rows to {a.out}\n")
    print("Links (packets, drops):")
    print(trace_links(ev).to_string(index=False))
    pc = path_changes(ev)
    if not pc.empty:
        print("\nRoutes taken (a new row = route changed):")
        print(pc.to_string(index=False))


if __name__ == "__main__":
    main()
