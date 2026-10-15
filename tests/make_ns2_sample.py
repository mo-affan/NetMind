"""Generate tests/data/sample_ns2.tr: a SYNTHETIC trace in the ns-2 wired trace format that
mimics ns2/netmind_scenario.tcl. It is produced by a small Python queue model, NOT by NS2,
so the parser and pipeline can be tested on machines without NS2.

What it imitates from the scenario:
  * TCP n0->n3 from 0.5 s to 9.5 s, window 6 packets, 1040-byte packets, ACK-clocked,
    a dropped segment is retransmitted (same seq, new packet id) after a 0.2 s timeout
  * TCP ACKs n3->n0 (type "ack", 40 bytes) and some rtProtoDV routing packets
  * UDP/CBR n1->n3 0.9 Mb/s from 3.0 s to 6.0 s (1000-byte packets)
  * bottleneck n2-n3 1 Mb/s 20 ms, DropTail queue of 10 packets
  * link n2-n3 down from 7.0 s to 8.5 s: packets queued for it or still on it are dropped
    at 7.0 s and new packets go n2-n4-n3 (1 Mb/s, 40 ms per link)

Run:  python tests/make_ns2_sample.py
"""
import heapq
from pathlib import Path

LINKS = {  # (u, v): (bandwidth bit/s, propagation s, queue limit packets)
    (0, 2): (2e6, 0.010, 50), (1, 2): (2e6, 0.010, 50),
    (2, 3): (1e6, 0.020, 10), (2, 4): (1e6, 0.040, 50), (4, 3): (1e6, 0.040, 50),
    (3, 2): (1e6, 0.020, 50), (2, 0): (2e6, 0.010, 50), (3, 4): (1e6, 0.040, 50), (4, 2): (1e6, 0.040, 50),
}
DOWN = (7.0, 8.5)
WINDOW, RTO = 6, 0.2


def link_down(t):
    return DOWN[0] <= t < DOWN[1]


class Net:
    def __init__(self):
        self.busy = {k: 0.0 for k in LINKS}
        self.lines = []
        self.pid = 0

    def send(self, t0, src, dst, typ, size, fid, seq, log=True):
        """Forward one packet hop by hop. Returns (delivery time or None, drop time or None)."""
        p = self.pid
        self.pid += 1
        node, a = src, t0
        fields = f"{typ} {size} ------- {fid} {src}.0 {dst}.0 {seq} {p}"
        while node != dst:
            if node in (0, 1):
                nxt = 2
            elif node == 2 and dst == 3:
                nxt = 4 if link_down(a) else 3
            elif node == 4:
                nxt = 3 if dst == 3 else 2
            elif node == 3:   # ACKs back to n0
                nxt = 4 if link_down(a) else 2
            else:
                nxt = 0
            bw, prop, limit = LINKS[(node, nxt)]
            svc = size * 8 / bw
            start = max(a, self.busy[(node, nxt)])
            if log:
                self.lines.append((a, f"+ {a:.6f} {node} {nxt} {fields}"))
            if (start - a) / svc >= limit:                       # queue full: DropTail
                if log:
                    self.lines.append((a, f"d {a:.6f} {node} {nxt} {fields}"))
                return None, a
            if {node, nxt} == {2, 3} and a < DOWN[0] < start + svc + prop:
                # waiting in the queue or still on the wire when the link failed: lost
                if log:
                    if start < DOWN[0]:
                        self.lines.append((start, f"- {start:.6f} {node} {nxt} {fields}"))
                    self.lines.append((DOWN[0], f"d {DOWN[0]:.6f} {node} {nxt} {fields}"))
                return None, DOWN[0]
            self.busy[(node, nxt)] = start + svc
            if log:
                self.lines.append((start, f"- {start:.6f} {node} {nxt} {fields}"))
            a = start + svc + prop
            if log:
                self.lines.append((a, f"r {a:.6f} {node} {nxt} {fields}"))
            node = nxt
        return a, None


def main(out="tests/data/sample_ns2.tr"):
    net = Net()
    cbr = [3.0 + i * 1000 * 8 / 0.9e6 for i in range(int(3.0 / (1000 * 8 / 0.9e6)))]
    slots = [0.5] * WINDOW           # times at which each window slot becomes free
    heapq.heapify(slots)
    retx = []                        # (due time, seq)
    seq, last_tcp = 0, 0.0
    ci = 0
    while True:
        free = slots[0]
        t_tcp = max(free, last_tcp + 1040 * 8 / 2e6)
        is_retx = bool(retx) and retx[0][0] <= t_tcp
        if is_retx:
            t_tcp = max(retx[0][0], last_tcp + 1040 * 8 / 2e6)
        t_cbr = cbr[ci] if ci < len(cbr) else float("inf")
        if min(t_tcp, t_cbr) >= 9.5 and t_cbr == float("inf"):
            break
        if t_cbr < t_tcp:
            net.send(t_cbr, 1, 3, "cbr", 1000, 2, ci, True)
            ci += 1
            continue
        if t_tcp >= 9.5:
            ci = len(cbr) if t_cbr >= 9.5 else ci
            if ci >= len(cbr):
                break
            continue
        if is_retx:
            _, s = heapq.heappop(retx)
        else:
            heapq.heappop(slots)
            s, seq = seq, seq + 1
        recv, dropped = net.send(t_tcp, 0, 3, "tcp", 1040, 1, s)
        last_tcp = t_tcp
        if recv is not None:
            ack_t, _ = net.send(recv, 3, 0, "ack", 40, 1, s)
            if not is_retx:
                heapq.heappush(slots, ack_t if ack_t else recv + 0.05)
        else:
            heapq.heappush(retx, (dropped + RTO, s))
            if not is_retx:
                heapq.heappush(slots, dropped + RTO + 0.1)
    for k in range(10):  # routing updates around the failure (the parser must skip them)
        t = DOWN[0] + k * 0.01
        net.lines.append((t, f"r {t:.6f} 2 4 rtProtoDV 7 ------- 0 2.1 4.1 -1 {900000 + k}"))
    net.lines.sort(key=lambda x: x[0])
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text("\n".join(l for _, l in net.lines) + "\n")
    print(f"wrote {len(net.lines)} lines to {out} (synthetic, not produced by NS2)")


if __name__ == "__main__":
    main()
