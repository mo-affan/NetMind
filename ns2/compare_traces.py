"""Compare two NS2 traces of netmind_scenario.tcl phase by phase (standard library only).

Typical use, DropTail vs RED on the bottleneck:

  ns netmind_scenario.tcl droptail DropTail
  ns netmind_scenario.tcl red RED
  python3 compare_traces.py droptail.tr red.tr

For each phase of the scenario it prints packets sent, dropped, loss, mean one-way delay and
TCP goodput (data delivered to n3), for both traces side by side.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_trace import analyse, load  # noqa: E402

PHASES = [("normal", 0.5, 3.0), ("UDP burst", 3.0, 6.0), ("recovery", 6.0, 7.0),
          ("link down", 7.0, 8.5), ("link up", 8.5, 10.0)]


def phase_stats(pk: dict, t0: float, t1: float) -> dict:
    sel = [p for p in pk.values() if t0 <= p["t"] < t1]
    got = [p for p in sel if p["recv"] is not None]
    drop = [p for p in sel if p["recv"] is None and p["drop"] is not None]
    known = len(got) + len(drop)
    tcp_bytes = sum(p["size"] for p in got if p["type"] == "tcp")
    return {"sent": len(sel), "drop": len(drop),
            "loss": 100 * len(drop) / known if known else 0.0,
            "delay": sum(p["recv"] - p["t"] for p in got) / len(got) * 1000 if got else 0.0,
            "tcp_mbps": tcp_bytes * 8 / (t1 - t0) / 1e6,
            "tcp_drop": sum(1 for p in drop if p["type"] == "tcp")}


def summarise(path: str) -> dict:
    events, _, _ = load(path)
    if not events:
        raise SystemExit(f"No packet events found in {path}. Is this the file written by `$ns trace-all`?")
    pk, _ = analyse(events)
    return {name: phase_stats(pk, t0, t1) for name, t0, t1 in PHASES}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trace_a")
    ap.add_argument("trace_b")
    a = ap.parse_args(argv)
    sa, sb = summarise(a.trace_a), summarise(a.trace_b)
    na, nb = Path(a.trace_a).stem, Path(a.trace_b).stem
    print(f"A = {a.trace_a}\nB = {a.trace_b}\n")
    head = f"{'phase':<10} {'':<2} {'sent':>5} {'drop':>5} {'loss%':>6} {'delay ms':>9} {'TCP Mb/s':>9} {'TCP drops':>9}"
    print(head)
    print("-" * len(head))
    for name, _, _ in PHASES:
        for tag, s in (("A", sa[name]), ("B", sb[name])):
            print(f"{name if tag == 'A' else '':<10} {tag:<2} {s['sent']:>5} {s['drop']:>5} {s['loss']:>6.2f} "
                  f"{s['delay']:>9.1f} {s['tcp_mbps']:>9.3f} {s['tcp_drop']:>9}")
    burst_a, burst_b = sa["UDP burst"], sb["UDP burst"]
    print(f"\nDuring the UDP burst: delay {burst_a['delay']:.1f} ms ({na}) vs {burst_b['delay']:.1f} ms ({nb}); "
          f"TCP goodput {burst_a['tcp_mbps']:.3f} vs {burst_b['tcp_mbps']:.3f} Mb/s.")
    print("A RED queue drops packets early, before the queue is full, so the queue stays shorter: "
          "expect lower delay than DropTail during the burst, with drops spread over both flows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
