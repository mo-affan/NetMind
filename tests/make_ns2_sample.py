"""Generate tests/data/sample_ns2.tr: a trace in exact NS2 wired format that mimics
ns2/netmind_scenario.tcl (TCP n0->n3, UDP burst 3-6 s, link n2-n3 down 7-8.5 s).

It is produced by a small queue simulation in Python, so the tests do not need NS2
installed. Run:  python tests/make_ns2_sample.py
"""
from pathlib import Path

LINKS = {  # (u, v): (bandwidth bit/s, propagation s, queue limit)
    (0, 2): (2e6, 0.010, 50), (1, 2): (2e6, 0.010, 50),
    (2, 3): (1e6, 0.020, 10), (2, 4): (1e6, 0.040, 50), (4, 3): (1e6, 0.040, 50),
}


def route(src, t):
    down = 7.0 <= t < 8.5
    return [src, 2, 4, 3] if down else [src, 2, 3]


def main(out="tests/data/sample_ns2.tr"):
    pkts = []
    pid = 0
    t = 0.5
    seq = 0
    while t < 9.5:  # TCP-like flow at 0.8 Mb/s
        pkts.append((t, 0, 3, "tcp", 1040, 1, seq, pid)); pid += 1; seq += 1
        t += 1040 * 8 / 0.8e6
    t, seq = 3.0, 0
    while t < 6.0:  # CBR burst 0.9 Mb/s
        pkts.append((t, 1, 3, "cbr", 1000, 2, seq, pid)); pid += 1; seq += 1
        t += 1000 * 8 / 0.9e6
    pkts.sort()
    busy = {k: 0.0 for k in LINKS}
    lines = []
    for (t0, src, dst, typ, size, fid, seq, p) in pkts:
        hops = route(src, t0)
        a = t0
        for u, v in zip(hops, hops[1:]):
            bw, prop, limit = LINKS[(u, v)]
            svc = size * 8 / bw
            start = max(a, busy[(u, v)])
            fields = f"{typ} {size} ------- {fid} {src}.0 {dst}.0 {seq} {p}"
            lines.append((a, f"+ {a:.6f} {u} {v} {fields}"))
            if (start - a) / svc >= limit:
                lines.append((a, f"d {a:.6f} {u} {v} {fields}"))
                break
            busy[(u, v)] = start + svc
            lines.append((start, f"- {start:.6f} {u} {v} {fields}"))
            a = start + svc + prop
            lines.append((a, f"r {a:.6f} {u} {v} {fields}"))
    # some routing and ack packets that the parser must ignore
    for k in range(10):
        lines.append((7.0 + k * 0.01, f"r {7.0 + k * 0.01:.6f} 2 4 rtProtoDV 7 ------- 0 2.1 4.1 -1 {900000 + k}"))
        lines.append((1.0 + k, f"r {1.0 + k:.6f} 3 2 ack 40 ------- 1 3.0 0.0 {k} {800000 + k}"))
    lines.sort(key=lambda x: x[0])
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text("\n".join(l for _, l in lines) + "\n")
    print(f"wrote {len(lines)} lines to {out}")


if __name__ == "__main__":
    main()
