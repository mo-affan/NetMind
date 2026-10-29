"""
NetMind - NS2 trace parser (command line, uses pandas)

Prints per-flow totals, per-window metrics (sent, delivered, dropped, loss %,
retransmissions, throughput, one-way delay, jitter), drops per link and route changes.
Definitions are in netmind/capture/ns2.py. No NS2 installation is needed to run this.

Usage (from the repo root):
  python ns2/parse_trace.py ns2/netmind.tr
  python ns2/parse_trace.py ns2/netmind.tr --window 0.5 --per-flow --out results.csv
Full analysis (database, anomaly detection, dashboard, Copilot):
  python -m netmind ns2 ns2/netmind.tr
On a machine without pandas, use the standard-library checker instead:
  python3 ns2/check_trace.py ns2/netmind.tr
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for `netmind`

import pandas as pd  # noqa: E402

from netmind.capture.ns2 import (flow_summary, path_changes, read_link_events,  # noqa: E402
                                 read_trace, trace_links, trace_metrics)

pd.set_option("display.width", 200)


def main():
    """Full trace parser: per-window table, per-flow totals, CSV output."""
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--window", type=float, default=1.0)
    ap.add_argument("--per-flow", action="store_true")
    ap.add_argument("--out", default="netmind_metrics.csv", help="CSV of the per-window table")
    a = ap.parse_args()

    ev = read_trace(a.trace)
    if ev.empty:
        print(f"No packet events found in {a.trace}. Is this the wired trace written by "
              "`$ns trace-all`? (The wireless new-trace format is not supported.)")
        sys.exit(1)
    print(f"Trace: {a.trace}  ({len(ev)} packet events, {ev['t'].min():.3f}-{ev['t'].max():.3f} s)\n")
    print("Per flow:")
    print(flow_summary(ev).to_string(index=False))
    m = trace_metrics(ev, a.window, per_flow=a.per_flow)
    m.to_csv(a.out, index=False)
    print(f"\nPer {a.window:g} s window (loss/delay by send time, throughput by delivery time):")
    print(m.to_string(index=False))
    print(f"\nSaved the window table to {a.out}\n")
    print("Links (data packets enqueued, drops):")
    print(trace_links(ev).to_string(index=False))
    pc = path_changes(ev)
    if not pc.empty:
        print("\nRoutes taken (a new row = route changed):")
        print(pc.to_string(index=False))
    le = read_link_events(a.trace)
    if not le.empty:
        print("\nLink status changes recorded in the trace:")
        print(le.to_string(index=False))


if __name__ == "__main__":
    main()
