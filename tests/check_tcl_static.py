"""Static checks for ns2/netmind_scenario.tcl, for machines without Tcl or NS2.

This does NOT run the simulation. It checks that braces/brackets/quotes balance, that
only known ns-2.35 OTcl methods are called, that every variable used is defined, that
trace-all is set before links are created, and that the scenario timeline is intact.
Run: python tests/check_tcl_static.py
"""
import re
import sys
from pathlib import Path

TCL = Path(__file__).resolve().parents[1] / "ns2" / "netmind_scenario.tcl"

SIM_METHODS = {"rtproto", "trace-all", "namtrace-all", "color", "node", "duplex-link", "cost",
               "queue-limit", "duplex-link-op", "attach-agent", "connect", "at", "rtmodel-at",
               "flush-trace", "run", "now"}
OBJ_METHODS = {"Node": {"label"}, "Agent": {"set"}, "App": {"set", "attach-agent", "start", "stop"}}
OBJECTS = {"n0": "Node", "n1": "Node", "n2": "Node", "n3": "Node", "n4": "Node", "tcp": "Agent",
           "udp": "Agent", "sink": "Agent", "null": "Agent", "cbr": "App", "ftp": "App"}


def check(path=TCL) -> list[str]:
    src = Path(path).read_text()
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    errors = []
    for o, c in ["{}", "[]"]:
        if code.count(o) != code.count(c):
            errors.append(f"unbalanced {o}{c}: {code.count(o)} vs {code.count(c)}")
    for i, line in enumerate(code.splitlines(), 1):
        if line.count('"') % 2:
            errors.append(f"odd number of quotes: {line.strip()}")
    for m in set(re.findall(r"\$ns ([\w-]+)", code)) - SIM_METHODS:
        errors.append(f"unknown Simulator method: $ns {m}")
    for line in code.splitlines():
        m = re.match(r"\s*\$(\w+) ([\w-]+)", line)
        if m and m.group(1) in OBJECTS and m.group(2) not in OBJ_METHODS[OBJECTS[m.group(1)]]:
            errors.append(f"unexpected method: {line.strip()}")
    defined = set(re.findall(r"\bset (\w+)", code)) | {"argc", "argv", "msg"}
    for v in set(re.findall(r"\$(\w+)", code)) - defined:
        errors.append(f"variable used but never set: ${v}")
    if code.index("trace-all") > code.index("duplex-link "):
        errors.append("trace-all must be called before links are created")
    expected = ['$ns at 0.5 "$ftp start"', '$ns at 3.0 "$cbr start"', '$ns at 6.0 "$cbr stop"',
                "$ns rtmodel-at 7.0 down $n2 $n3", "$ns rtmodel-at 8.5 up $n2 $n3",
                '$ns at 9.5 "$ftp stop"', '$ns at 10.0 "finish"', "$ns rtproto DV",
                "$ns queue-limit $n2 $n3 10", "exit 0", "close $tracefile"]
    for e in expected:
        if e not in code:
            errors.append(f"missing: {e}")
    return errors


if __name__ == "__main__":
    errs = check()
    print("\n".join(errs) if errs else f"static checks passed: {TCL.name} (NOT executed; needs NS2)")
    sys.exit(1 if errs else 0)
