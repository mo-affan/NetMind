"""Logic behind the dashboard's NS2 lab page (no Streamlit, so it can be tested anywhere).

It reuses the lab tools in ns2/ (check_trace.py and compare_traces.py, standard library only),
so the page shows exactly what `python3 check_trace.py` prints in the lab.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pandas as pd

NS2_DIR = Path(__file__).resolve().parents[2] / "ns2"
SCENARIO = NS2_DIR / "netmind_scenario.tcl"
SAMPLE_TRACE = NS2_DIR.parent / "tests" / "data" / "sample_ns2.tr"

TIMELINE = [  # from netmind_scenario.tcl
    ("0.5 s", "TCP (FTP) n0 → n3 starts, window 6 packets", "No drops, normal delay"),
    ("3.0 s", "UDP (CBR 0.9 Mb/s) n1 → n3 starts on the 1 Mb n2-n3 bottleneck", "Queue fills: drops, delay rises"),
    ("6.0 s", "UDP stops", "Network recovers"),
    ("7.0 s", "Link n2-n3 goes down", "Distance Vector reroutes TCP via n2-n4-n3"),
    ("8.5 s", "Link n2-n3 comes back up", "TCP returns to n2-n3"),
    ("10.0 s", "Simulation ends", "netmind.tr and netmind.nam are written"),
]

COMMANDS = """# Ubuntu terminal, in the folder that holds the scenario files
cd ~/netmind_ns2
cp ~/NetMind/ns2/netmind_scenario.tcl ~/NetMind/ns2/check_trace.py ~/NetMind/ns2/compare_traces.py .

ns netmind_scenario.tcl                 # DropTail bottleneck -> netmind.tr, netmind.nam
python3 check_trace.py netmind.tr       # the five scenario checks

ns netmind_scenario.tcl red RED         # RED bottleneck -> red.tr, red.nam
python3 compare_traces.py netmind.tr red.tr

nam netmind.nam                         # optional: the animation"""


def _load(name: str):
    """Import one of the ns2/ scripts as a module (they are not part of the netmind package)."""
    key = f"netmind_ns2_{name}"
    if key in sys.modules:
        return sys.modules[key]
    if str(NS2_DIR) not in sys.path:  # compare_traces imports check_trace by name
        sys.path.insert(0, str(NS2_DIR))
    spec = importlib.util.spec_from_file_location(key, NS2_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules[key] = mod
    return mod


def scenario_source() -> str:
    """The text of netmind_scenario.tcl."""
    return SCENARIO.read_text()


def scenario_parameters(src: str | None = None) -> dict:
    """Key settings read from the TCL file itself, so the page never disagrees with the script."""
    src = src or scenario_source()
    links = re.findall(r"\$ns duplex-link \$(n\d) \$(n\d) (\S+) (\S+) (\S+)", src)
    window = re.search(r"\$tcp set window_ (\d+)", src)
    rate = re.search(r"\$cbr set rate_ (\S+)", src)
    qlim = re.search(r"\$ns queue-limit \$n2 \$n3 (\d+)", src)
    costs = re.findall(r"\$ns cost \$(n\d) \$(n\d) (\d+)", src)
    return {"links": [{"a": a, "b": b, "bandwidth": bw, "delay": d, "queue": q} for a, b, bw, d, q in links],
            "tcp_window": int(window.group(1)) if window else None,
            "udp_rate": rate.group(1) if rate else None,
            "queue_limit": int(qlim.group(1)) if qlim else None,
            "costs": sorted({(min(a, b), max(a, b), int(c)) for a, b, c in costs}),
            "routing": "Distance Vector" if "rtproto DV" in src else "static"}


def check(path: str | Path) -> dict:
    """The lab checker's results for one trace: the five checks, their numbers, drops per link, routes."""
    ct = _load("check_trace")
    events, link_lines, other = ct.load(str(path))
    if not events:
        raise ValueError("no packet events found: is this the .tr file written by `$ns trace-all`?")
    pk, hops = ct.analyse(events)
    checks, stats = ct.scenario_checks(pk, hops)
    per_link: dict[str, int] = {}
    for p in pk.values():
        if p["recv"] is None and p["drop"] is not None:
            per_link[p["drop_link"]] = per_link.get(p["drop_link"], 0) + 1
    return {"checks": checks, "stats": stats, "passed": sum(ok for _, ok in checks),
            "events": len(events), "packets": len(pk), "t_end": max(e[1] for e in events),
            "drops_per_link": per_link, "routes": ct.routes(pk, hops), "skipped": dict(other)}


def phases(path: str | Path) -> pd.DataFrame:
    """Sent, drops, loss, delay and TCP goodput per scenario phase (compare_traces.py)."""
    cmp = _load("compare_traces")
    s = cmp.summarise(str(path))
    rows = [{"Phase": name, "From (s)": t0, "To (s)": t1, "Sent": s[name]["sent"], "Drops": s[name]["drop"],
             "Loss %": round(s[name]["loss"], 2), "Delay (ms)": round(s[name]["delay"], 1),
             "TCP goodput (Mb/s)": round(s[name]["tcp_mbps"], 3), "TCP drops": s[name]["tcp_drop"]}
            for name, t0, t1 in cmp.PHASES]
    return pd.DataFrame(rows)


def compare(path_a: str | Path, path_b: str | Path, name_a: str = "A", name_b: str = "B") -> pd.DataFrame:
    """Phase table of two traces side by side, with the change from A to B."""
    a, b = phases(path_a), phases(path_b)
    out = pd.DataFrame({"Phase": a["Phase"]})
    for col in ("Delay (ms)", "Drops", "Loss %", "TCP goodput (Mb/s)"):
        out[f"{col} {name_a}"] = a[col]
        out[f"{col} {name_b}"] = b[col]
    base = a["Delay (ms)"].where(a["Delay (ms)"] > 0)
    out["Delay change %"] = (100 * (b["Delay (ms)"] - a["Delay (ms)"]) / base).round(1)
    return out
