"""NetMind command line.

    python -m netmind demo                       # synthetic traffic with 3 known problems
    python -m netmind capture --duration 60      # live capture (needs admin rights)
    python -m netmind pcap capture.pcap          # analyse a Wireshark/tcpdump file
    python -m netmind ns2 ns2/netmind.tr         # analyse an NS2 trace
    python -m netmind runs                       # list saved runs
    python -m netmind report [--run N]           # metrics and incidents of a run
    python -m netmind ask "Why is the network slow?" [--run N]
    python -m netmind routes [--run N] [--from A --to B]
    python -m netmind api                        # REST API on http://127.0.0.1:8000
    python -m netmind dashboard                  # Streamlit dashboard
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)


def _db(args):
    from netmind.storage import NetMindDB
    return NetMindDB(args.db)


def _print_report(db, run_id: int) -> None:
    from netmind.pipeline import get_state
    st = get_state(db, run_id)
    run, s, o = st["run"], st["summary"], st["overall"]
    print(f"\n=== Run {run['id']}: {run['name']} ({run['source']}) ===")
    print(f"Packets {s.get('packets')}  bytes {s.get('bytes')}  duration {s.get('duration_s')} s  "
          f"hosts {s.get('hosts')}  flows {s.get('flows')}")
    print("Protocols:", s.get("protocols"))
    print("Overall:", {k: v for k, v in o.items() if v is not None})
    m = db.load("metrics", run_id)
    if not m.empty:
        cols = [c for c in ("t", "pps", "throughput_mbps", "latency_ms", "jitter_ms", "loss_pct",
                            "retransmissions") if c in m.columns]
        a = db.load("anomalies", run_id)
        if not a.empty:
            m = m.merge(a[["t", "anomaly_score", "is_anomaly"]], on="t", how="left")
            cols += ["anomaly_score", "is_anomaly"]
        step = max(1, len(m) // 30)
        print(f"\nPer-window metrics (every {step} window(s)):")
        print(m[cols].iloc[::step].to_string(index=False))
    print("\nIncidents:")
    if not st["incidents"]:
        print("  none: all windows look normal")
    for e in st["incidents"]:
        feats = ", ".join(f"{f['feature']} {f['value']:g} (normal {f['normal']:g})"
                          for f in e["top_features"])
        print(f"  * {e['title']}: t={e['start_t']:g}-{e['end_t']:g} s, score {e['peak_score']:.2f}, "
              f"{e['top_proto']} {e['top_src']} -> {e['top_dst']}\n      {feats}")
    for r in st["routes"]:
        print(f"  route t={r['t']:.2f} s flow {r['fid']}: {r['path']}")


def cmd_demo(args):
    from netmind.capture.records import to_frame
    from netmind.capture.synthetic import generate_scenario, to_pcap
    from netmind.pipeline import analyze_packets
    recs, events = generate_scenario(duration=args.duration, seed=args.seed)
    if args.save_pcap:
        Path(args.save_pcap).parent.mkdir(parents=True, exist_ok=True)
        try:
            to_pcap(recs, args.save_pcap)
            print(f"Saved demo traffic to {args.save_pcap} (open it in Wireshark)")
        except ImportError:
            print("Scapy not installed: skipping pcap export")
    df = to_frame(recs)
    print(f"Generated {len(df)} packets. Injected events:")
    t0 = df["ts"].min()
    for s, e, n in events:
        print(f"  {n:<11} t={s - t0:g}-{e - t0:g} s")
    db = _db(args)
    run_id = analyze_packets(df, "demo", "demo", db, train_until=60)
    _print_report(db, run_id)
    print(f"\nSaved as run {run_id} in {args.db}. Try:  python -m netmind ask \"Why is the network slow?\"")


def cmd_capture(args):
    from netmind.capture.sniffer import live_capture
    from netmind.pipeline import analyze_packets
    print(f"Capturing on {args.iface or 'default interface'} for {args.duration} s "
          f"(filter: {args.filter})... Ctrl+C to stop early.")
    df = live_capture(args.iface, count=args.count, timeout=args.duration, bpf=args.filter,
                      save_pcap=args.save_pcap)
    if df.empty:
        print("No IP packets captured. Check the interface name (python -m netmind interfaces) "
              "and that you run as administrator.")
        return
    model = _load_model(args.model)
    db = _db(args)
    run_id = analyze_packets(df, args.name or "live capture", "live", db, window=args.window,
                             model=model, link_capacity_mbps=args.capacity)
    _print_report(db, run_id)


def _load_model(path):
    if not path:
        return None
    from netmind.anomaly import AnomalyDetector
    print(f"Using trained anomaly model {path}")
    return AnomalyDetector.load(path)


def cmd_pcap(args):
    from netmind.capture.sniffer import read_pcap
    from netmind.pipeline import analyze_packets
    df = read_pcap(args.file)
    print(f"Read {len(df)} IP packets from {args.file}")
    db = _db(args)
    run_id = analyze_packets(df, args.name or Path(args.file).name, "pcap", db, window=args.window,
                             train_until=args.train_until, model=_load_model(args.model),
                             link_capacity_mbps=args.capacity)
    _print_report(db, run_id)


def cmd_ns2(args):
    from netmind.pipeline import analyze_ns2
    db = _db(args)
    run_id = analyze_ns2(args.trace, args.name, db, window=args.window, train_until=args.train_until)
    _print_report(db, run_id)


def cmd_runs(args):
    db = _db(args)
    r = db.runs()
    if r.empty:
        print("No runs yet. Start with:  python -m netmind demo")
        return
    r["created"] = pd.to_datetime(r["created"], unit="s").dt.strftime("%Y-%m-%d %H:%M")
    print(r.to_string(index=False))


def cmd_report(args):
    db = _db(args)
    run_id = args.run or db.latest_run_id()
    if run_id is None:
        print("No runs yet. Start with:  python -m netmind demo")
        return
    _print_report(db, run_id)


def cmd_ask(args):
    from netmind.copilot import Copilot
    from netmind.pipeline import get_state
    db = _db(args)
    state = get_state(db, args.run)
    if not state["run"]:
        print("No runs yet. Start with:  python -m netmind demo")
        return
    c = Copilot(backend=args.backend)
    res = c.ask(args.question, state)
    print(f"[run {state['run']['id']}: {state['run']['name']} | backend: {res['backend']}]\n")
    print(res["answer"])
    if args.show_prompt:
        print("\n--- prompt sent to the LLM ---\n" + res["prompt"])


def cmd_routes(args):
    from netmind.topology import (distance_vector_tables, graph_from_frames, link_state_tables,
                                  shortest_path)
    db = _db(args)
    run_id = args.run or db.latest_run_id()
    G = graph_from_frames(db.load("nodes", run_id), db.load("links", run_id))
    w = args.weight
    print(f"Topology of run {run_id}: {G.number_of_nodes()} nodes, {G.number_of_edges()} links")
    if args.src and args.dst:
        print("Dijkstra:", shortest_path(G, args.src, args.dst, weight=w))
    ls = link_state_tables(G, w)
    dv, rounds = distance_vector_tables(G, w)
    node = args.src or next(iter(G.nodes))
    print(f"\nRouting table of {node} (weight = {w})")
    print(f"{'destination':<18}{'LS next hop':<18}{'LS cost':>9}   {'DV next hop':<18}{'DV cost':>9}")
    for d in sorted(ls[node]):
        print(f"{d:<18}{ls[node][d]['next_hop']:<18}{ls[node][d]['cost']:>9}   "
              f"{dv[node][d]['next_hop']:<18}{dv[node][d]['cost']:>9}")
    print(f"\nDistance Vector converged after {rounds} exchange round(s).")


def cmd_interfaces(args):
    from netmind.capture.sniffer import list_interfaces
    for i in list_interfaces():
        print(i)


def cmd_api(args):
    import uvicorn
    import os
    os.environ["NETMIND_DB"] = args.db
    uvicorn.run("netmind.api:app", host=args.host, port=args.port)


def cmd_dashboard(args):
    app = Path(__file__).parent / "dashboard" / "app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app), "--", "--db", args.db])


def main(argv=None):
    from netmind.storage import DEFAULT_DB
    p = argparse.ArgumentParser(prog="netmind", description="NetMind network intelligence")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database (default data/netmind.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="analyse synthetic traffic with known problems")
    d.add_argument("--duration", type=float, default=180)
    d.add_argument("--seed", type=int, default=7)
    d.add_argument("--save-pcap", default="data/demo.pcap")
    d.set_defaults(func=cmd_demo)

    c = sub.add_parser("capture", help="live capture and analyse (admin rights needed)")
    c.add_argument("--iface")
    c.add_argument("--duration", type=int, default=60)
    c.add_argument("--count", type=int, default=0)
    c.add_argument("--filter", default="ip")
    c.add_argument("--save-pcap")
    c.add_argument("--model", help="trained anomaly model (.joblib) to use instead of training")
    c.add_argument("--name")
    c.add_argument("--window", type=float, default=2.0)
    c.add_argument("--capacity", type=float, default=100.0, help="link capacity in Mbps")
    c.set_defaults(func=cmd_capture)

    f = sub.add_parser("pcap", help="analyse a .pcap/.pcapng file")
    f.add_argument("file")
    f.add_argument("--name")
    f.add_argument("--window", type=float, default=2.0)
    f.add_argument("--train-until", type=float, help="seconds of normal traffic at the start")
    f.add_argument("--model")
    f.add_argument("--capacity", type=float, default=100.0)
    f.set_defaults(func=cmd_pcap)

    n = sub.add_parser("ns2", help="analyse an NS2 trace file")
    n.add_argument("trace")
    n.add_argument("--name")
    n.add_argument("--window", type=float, default=0.5)
    n.add_argument("--train-until", type=float, default=3.0)
    n.set_defaults(func=cmd_ns2)

    sub.add_parser("runs", help="list saved runs").set_defaults(func=cmd_runs)
    r = sub.add_parser("report", help="print a run's report")
    r.add_argument("--run", type=int)
    r.set_defaults(func=cmd_report)

    a = sub.add_parser("ask", help="ask the Copilot about a run")
    a.add_argument("question")
    a.add_argument("--run", type=int)
    a.add_argument("--backend", choices=["anthropic", "ollama", "offline"])
    a.add_argument("--show-prompt", action="store_true")
    a.set_defaults(func=cmd_ask)

    t = sub.add_parser("routes", help="shortest path and LS/DV routing tables")
    t.add_argument("--run", type=int)
    t.add_argument("--from", dest="src")
    t.add_argument("--to", dest="dst")
    t.add_argument("--weight", default="latency", choices=["latency", "hops"])
    t.set_defaults(func=cmd_routes)

    sub.add_parser("interfaces", help="list capture interfaces").set_defaults(func=cmd_interfaces)
    ap = sub.add_parser("api", help="start the REST API")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.set_defaults(func=cmd_api)
    sub.add_parser("dashboard", help="start the Streamlit dashboard").set_defaults(func=cmd_dashboard)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
