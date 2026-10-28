"""Builds the two Review 2 study notes: one for Affan, one for Hardik.

Each PDF = Part A (the essentials both must know, identical in both) + Part B (that person's
slides, demo segment and viva questions). Run: python docs/review-2/build_split_notes.py
Needs reportlab; Inter TTFs in FONT_DIR (converted from the system's Inter OTFs), else DejaVu.
"""
from __future__ import annotations

import os
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, Flowable, KeepTogether, PageBreak, Paragraph,
                                Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle)

HERE = Path(__file__).resolve().parent
FONT_DIR = Path(os.environ.get("NETMIND_FONT_DIR", HERE / "fonts"))
DV = "/usr/share/fonts/truetype/dejavu/"


def _font(name, inter, fallback):
    p = FONT_DIR / inter
    pdfmetrics.registerFont(TTFont(name, str(p) if p.exists() else DV + fallback))


_font("Body", "Inter-Regular.ttf", "DejaVuSans.ttf")
_font("Body-Medium", "Inter-Medium.ttf", "DejaVuSans.ttf")
_font("Body-Semi", "Inter-SemiBold.ttf", "DejaVuSans-Bold.ttf")
_font("Body-Bold", "Inter-Bold.ttf", "DejaVuSans-Bold.ttf")
pdfmetrics.registerFont(TTFont("Mono", DV + "DejaVuSansMono.ttf"))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Semi", italic="Body", boldItalic="Body-Semi")

# ---------------------------------------------------------------- palette
INK = colors.HexColor("#14212B")
SOFT = colors.HexColor("#4A5863")
MUTED = colors.HexColor("#7A8790")
LINE = colors.HexColor("#DCE3E6")
CARD = colors.HexColor("#F4F7F8")
NIGHT = colors.HexColor("#0F1A20")
TEAL = colors.HexColor("#0B6E78")
TEAL_L = colors.HexColor("#DDF0F1")
CYAN = colors.HexColor("#2FC1CB")
RED = colors.HexColor("#C23434")
RED_L = colors.HexColor("#FBEAEA")
GREEN = colors.HexColor("#1D7A3E")
PEOPLE = {
    "Affan": {"full": "Mohammed Affan", "reg": "24BAI0014", "c": colors.HexColor("#2468C8"),
              "l": colors.HexColor("#E4EEFB")},
    "Hardik": {"full": "Hardik", "reg": "24BCI0017", "c": colors.HexColor("#C4541F"),
               "l": colors.HexColor("#FCECE3")},
}
BOTH = {"c": colors.HexColor("#6B4FB8"), "l": colors.HexColor("#EEE9FA")}

W = A4[0] - 36 * mm

S = {
    "h1": ParagraphStyle("h1", fontName="Body-Bold", fontSize=19, leading=23, textColor=INK, spaceAfter=2),
    "h2": ParagraphStyle("h2", fontName="Body-Semi", fontSize=12.5, leading=16, textColor=INK,
                         spaceBefore=8, spaceAfter=4),
    "body": ParagraphStyle("b", fontName="Body", fontSize=9.4, leading=13.6, textColor=INK, spaceAfter=4),
    "soft": ParagraphStyle("sf", fontName="Body", fontSize=9.2, leading=13.2, textColor=SOFT, spaceAfter=4),
    "small": ParagraphStyle("sm", fontName="Body", fontSize=8, leading=11, textColor=MUTED),
    "cell": ParagraphStyle("c", fontName="Body", fontSize=8.6, leading=11.8, textColor=INK),
    "cellh": ParagraphStyle("ch", fontName="Body-Semi", fontSize=8.6, leading=11.8, textColor=colors.white),
    "cellb": ParagraphStyle("cb", fontName="Body-Semi", fontSize=8.6, leading=11.8, textColor=INK),
    "quote": ParagraphStyle("q", fontName="Body-Medium", fontSize=10.4, leading=15.4, textColor=INK),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=7.8, leading=10.4, textColor=INK),
    "tilev": ParagraphStyle("tv", fontName="Body-Bold", fontSize=19, leading=22, alignment=TA_CENTER),
    "tilel": ParagraphStyle("tl", fontName="Body", fontSize=7.8, leading=10.2, textColor=SOFT, alignment=TA_CENTER),
}


def P(t, s="body", **kw):
    return Paragraph(t, ParagraphStyle("x", parent=S[s], **kw) if kw else S[s])


def bullets(items, s="body", colour=TEAL):
    hexc = colour.hexval()[2:]
    return [Paragraph(f'<font color="#{hexc}">●</font>&nbsp;&nbsp;{i}',
                      ParagraphStyle("bl", parent=S[s], leftIndent=11, firstLineIndent=-11, spaceAfter=2.6))
            for i in items]


def table(rows, widths, head=TEAL, zebra=True, header=True):
    data = [[P(c, "cellh" if header and r == 0 else "cell") if isinstance(c, str) else c for c in row]
            for r, row in enumerate(rows)]
    t = Table(data, colWidths=[w * W for w in widths], repeatRows=1 if header else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4.5),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5), ("LEFTPADDING", (0, 0), (-1, -1), 6),
          ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
          ("ROUNDEDCORNERS", [5, 5, 5, 5]), ("BOX", (0, 0), (-1, -1), 0.4, LINE)]
    if header:
        st.append(("BACKGROUND", (0, 0), (-1, 0), head))
    if zebra:
        for r in range(1 if header else 0, len(rows)):
            if (r % 2 == 0) == header:
                st.append(("BACKGROUND", (0, r), (-1, r), CARD))
    t.setStyle(TableStyle(st))
    return t


def box(flowables, bg=TEAL_L, bar=TEAL, pad=9, width=W):
    t = Table([[flowables]], colWidths=[width])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LINEBEFORE", (0, 0), (0, -1), 3.2, bar),
                           ("LEFTPADDING", (0, 0), (-1, -1), pad + 3), ("RIGHTPADDING", (0, 0), (-1, -1), pad),
                           ("TOPPADDING", (0, 0), (-1, -1), pad - 2), ("BOTTOMPADDING", (0, 0), (-1, -1), pad - 2),
                           ("ROUNDEDCORNERS", [4, 4, 4, 4])]))
    return t


def short(text, colour=TEAL, light=TEAL_L):
    hexc = colour.hexval()[2:]
    return KeepTogether([Spacer(1, 3), box([P(f'<font name="Body-Bold" color="#{hexc}">In short</font>&nbsp;&nbsp;{text}',
                                               "body", spaceAfter=0)], bg=light, bar=colour), Spacer(1, 6)])


def code(text):
    t = Table([[Preformatted(text, S["code"])]], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF2F4")),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("ROUNDEDCORNERS", [4, 4, 4, 4])]))
    return KeepTogether([t, Spacer(1, 6)])


def tiles(items, colour=TEAL):
    """Row of big-number tiles: (value, label)."""
    cells = [[P(f'<font color="#{colour.hexval()[2:]}">{v}</font>', "tilev"), P(lbl, "tilel")] for v, lbl in items]
    t = Table([cells], colWidths=[W / len(items)] * len(items))
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4),
          ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    t.setStyle(TableStyle(st))
    inner = []
    for c in cells:
        x = Table([[c[0]], [c[1]]], colWidths=[W / len(items) - 8])
        x.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CARD), ("ROUNDEDCORNERS", [6, 6, 6, 6]),
                               ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        inner.append(x)
    row = Table([inner], colWidths=[W / len(items)] * len(items))
    row.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                             ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return KeepTogether([row, Spacer(1, 8)])


class Heading(Flowable):
    """Section heading with a coloured number badge."""

    def __init__(self, num, title, colour=TEAL):
        super().__init__()
        self.num, self.title, self.colour = num, title, colour
        self.height = 30

    def wrap(self, aw, ah):
        return aw, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(self.colour)
        c.roundRect(0, 4, 24, 22, 5, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Body-Bold", 11)
        c.drawCentredString(12, 11, str(self.num))
        c.setFillColor(INK)
        c.setFont("Body-Bold", 16)
        c.drawString(34, 9.5, self.title)


def H(num, title, colour=TEAL):
    return [CondPageBreak(60 * mm), Spacer(1, 6), Heading(num, title, colour), Spacer(1, 4)]


class PartBanner(Flowable):
    def __init__(self, label, title, sub, colour):
        super().__init__()
        self.label, self.title, self.sub, self.colour = label, title, sub, colour

    def wrap(self, aw, ah):
        self.w = aw
        return aw, 74

    def draw(self):
        c = self.canv
        c.setFillColor(self.colour)
        c.roundRect(0, 0, self.w, 70, 8, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Body-Semi", 9)
        c.drawString(16, 50, self.label.upper())
        c.setFont("Body-Bold", 20)
        c.drawString(16, 27, self.title)
        c.setFont("Body", 9.5)
        c.drawString(16, 11, self.sub)


class SlideCard(Flowable):
    """Slide number badge + title, then the content table below (handled separately)."""

    def __init__(self, num, title, colour):
        super().__init__()
        self.num, self.title, self.colour = num, title, colour

    def wrap(self, aw, ah):
        self.w = aw
        return aw, 26

    def draw(self):
        c = self.canv
        c.setFillColor(self.colour)
        c.roundRect(0, 2, 58, 20, 4, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Body-Bold", 9)
        c.drawCentredString(29, 8.5, f"SLIDE {self.num}")
        c.setFillColor(INK)
        c.setFont("Body-Bold", 13)
        c.drawString(68, 7.5, self.title)


def slide(num, title, person, say, know, asked=None, extra=None):
    p = PEOPLE[person]
    parts = [CondPageBreak(55 * mm), Spacer(1, 6), SlideCard(num, title, p["c"]), Spacer(1, 4),
             box([P(f'<font name="Body-Semi" color="#{p["c"].hexval()[2:]}">Say</font>&nbsp;&nbsp;{say}',
                    "quote", spaceAfter=0)], bg=p["l"], bar=p["c"]), Spacer(1, 5),
             P('<font name="Body-Semi">What you need to know</font>', "body", spaceAfter=2)]
    parts += bullets(know, colour=p["c"])
    if extra:
        parts += extra
    if asked:
        parts.append(Spacer(1, 2))
        for q, a in asked:
            parts.append(P(f'<font name="Body-Semi" color="#{p["c"].hexval()[2:]}">If asked:</font> '
                           f'<i>{q}</i> {a}', "soft", spaceAfter=2.5))
    parts.append(Spacer(1, 6))
    return parts


def flow_diagram():
    d = Drawing(W, 214)
    edge = colors.HexColor("#8C9AA3")

    def node(x, y, w, h, title, sub="", main=False):
        d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=TEAL_L if main else colors.white,
                   strokeColor=TEAL if main else edge, strokeWidth=1.4 if main else 0.8))
        d.add(String(x + w / 2, y + h - 13, title, fontName="Body-Semi", fontSize=8.4, fillColor=INK,
                     textAnchor="middle"))
        if sub:
            d.add(String(x + w / 2, y + 7, sub, fontName="Body", fontSize=7, fillColor=SOFT, textAnchor="middle"))

    def arrow(x1, y1, x2, y2):
        d.add(Line(x1, y1, x2, y2, strokeColor=edge, strokeWidth=0.8))
        import math
        a = math.atan2(y2 - y1, x2 - x1)
        L, wd = 5, 2.6
        p1 = (x2 - L * math.cos(a) + wd * math.sin(a), y2 - L * math.sin(a) - wd * math.cos(a))
        p2 = (x2 - L * math.cos(a) - wd * math.sin(a), y2 - L * math.sin(a) + wd * math.cos(a))
        d.add(Polygon([x2, y2, *p1, *p2], fillColor=edge, strokeColor=edge, strokeWidth=0.1))

    cw = W
    iw = (cw - 3 * 8) / 4
    for i, t in enumerate(["Synthetic demo", "pcap file", "Live capture", "NS2 trace"]):
        node(i * (iw + 8), 186, iw, 22, t)
        arrow(i * (iw + 8) + iw / 2, 186, cw / 2 - 60 + i * 40, 166)
    node(cw / 2 - 130, 140, 260, 26, "1  Packet records", "one row per packet, same columns for every input", True)
    bw = (cw - 2 * 10) / 3
    labels = [("2  Traffic analysis", "protocols, flows, hosts, connections, DNS"),
              ("2  Performance, every 2 s", "latency, loss, jitter, throughput, health"),
              ("2  Topology and routing", "graph, Dijkstra, Link State, DV")]
    for i, (t, s) in enumerate(labels):
        x = i * (bw + 10)
        node(x, 92, bw, 30, t, s)
        arrow(cw / 2 - 40 + i * 40, 140, x + bw / 2, 122)
    node(cw / 2 - 130, 48, 260, 28, "3  Anomaly detection", "Isolation Forest + z-score, then incidents")
    arrow(bw / 2, 92, cw / 2 - 60, 76)
    arrow(bw + 10 + bw / 2, 92, cw / 2, 76)
    node(cw / 2 - 90, 12, 180, 22, "4  SQLite: one run per analysis")
    arrow(cw / 2, 48, cw / 2, 34)
    arrow(2 * (bw + 10) + bw / 2, 92, cw / 2 + 90, 23)
    node(0, 12, 120, 22, "5  Dashboard")
    node(cw - 120, 12, 120, 22, "5  Copilot + RAG")
    arrow(cw / 2 - 90, 23, 120, 23)
    arrow(cw / 2 + 90 + 0.1, 18, cw - 120, 18)
    return d


# ================================================================ PART A (shared)
def part_a():
    f = []
    f.append(PartBanner("Part A, for both of us", "The essentials",
                        "Read all of this. Either of us can be asked about any of it.", TEAL))
    f.append(Spacer(1, 10))

    f += H(1, "The 30-second pitch")
    f.append(box([P("“Network monitoring tools show numbers like latency and packet loss, but leave it to the "
                    "user to work out what is wrong. <b>NetMind measures a network from its own traffic, detects "
                    "unusual behaviour with an Isolation Forest model, and explains it in plain language</b> "
                    "through a Copilot that combines the measurements with a networking knowledge base. We test "
                    "it with real captures, an NS2 simulation with congestion and a link failure at known times, "
                    "and a synthetic demo with three known problems, so we can check that what NetMind finds "
                    "matches the truth.”", "quote", spaceAfter=0)], bg=CARD, bar=INK, pad=11))
    f.append(Spacer(1, 6))
    f.append(P("Project: <b>NetMind, AI-Powered Network Intelligence and LLM Network Copilot</b>. Computer "
               "Networks Lab (BCSE308P), VIT Vellore. Mohammed Affan (24BAI0014) and Hardik (24BCI0017). "
               "Code: github.com/mo-affan/NetMind.", "soft"))

    f += H(2, "What NetMind does")
    three = [("Measure", "Reads traffic and computes protocols, flows, latency, loss, jitter and throughput "
                         "every 2 s. No probes are sent."),
             ("Detect", "Learns normal traffic, flags windows far from it with Isolation Forest + a z-score, "
                        "and groups them into incidents."),
             ("Explain", "A Copilot answers “why is my network slow?” from the data and cited networking notes. "
                         "It only advises.")]
    cells = []
    for t, d_ in three:
        x = Table([[P(f'<font name="Body-Bold" size="12" color="#0B6E78">{t}</font>', "body", spaceAfter=1)],
                   [P(d_, "soft", spaceAfter=0)]], colWidths=[W / 3 - 10])
        x.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CARD), ("ROUNDEDCORNERS", [6, 6, 6, 6]),
                               ("LEFTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (0, 0), 8),
                               ("BOTTOMPADDING", (0, -1), (-1, -1), 9), ("LINEABOVE", (0, 0), (-1, 0), 3, TEAL)]))
        cells.append(x)
    row = Table([cells], colWidths=[W / 3] * 3)
    row.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                             ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    f += [row, Spacer(1, 4)]
    f.append(P("Five objectives: <b>Measure</b>, <b>Detect</b>, <b>Explain</b>, <b>Route</b> (topology, Dijkstra, "
               "Link State vs Distance Vector) and <b>Simulate</b> (NS2, added after the Review 1 feedback).", "body"))
    f.append(short("networking does the measuring; the AI only interprets what was measured."))

    f += H(3, "How it works, end to end")
    f.append(flow_diagram())
    f.append(Spacer(1, 4))
    f.append(P("Every input becomes <b>one packet table</b> (time, addresses, ports, protocol, length, TCP flags and "
               "sequence numbers, ICMP and DNS ids). Three analyses run on it side by side; the detector compares "
               "each window with the normal baseline; <font face='Mono' size='8.4'>pipeline.py</font> saves "
               "everything as one run in SQLite; the dashboard, command line, API and Copilot read that run.", "body"))
    f.append(short("packets in → one table → measure → detect → store → explain."))

    f += H(4, "Project structure")
    f.append(table([
        ["Module", "Folder", "What it does", "Built by"],
        ["M1 Capture", "netmind/capture/", "records.py (the table), sniffer.py (Scapy), ns2.py, synthetic.py (demo)", "Hardik"],
        ["M2 Traffic", "netmind/analyzer/", "protocols, flows (5-tuple); insights.py: connections, DNS, hosts, health", "Hardik"],
        ["M3 Anomaly", "netmind/anomaly/", "features, Isolation Forest, z-score, incidents", "Affan"],
        ["M4 Performance", "netmind/performance/", "latency, loss, jitter, throughput per window", "Affan"],
        ["M5 Topology", "netmind/topology/", "host graph, Dijkstra, Link State, Distance Vector", "Hardik"],
        ["M6 Storage", "netmind/storage/", "SQLite database of runs", "Hardik"],
        ["M7 RAG", "netmind/rag/", "9 networking notes, TF-IDF search", "Affan"],
        ["M8 Copilot", "netmind/copilot/", "prompt building, offline / Claude / Ollama answers", "Affan"],
        ["M9 Dashboard", "netmind/dashboard/", "Streamlit, 10 pages, light and dark", "Hardik"],
        ["NS2", "ns2/", "scenario .tcl, check_trace.py, compare_traces.py", "Affan"],
        ["Glue", "netmind/", "pipeline.py (runs it all), api.py (REST), __main__.py (CLI)", "Both"],
    ], [0.15, 0.22, 0.5, 0.13]))
    f.append(Spacer(1, 6))
    f.append(short("one folder per module, one file that runs them all (pipeline.py), one database, three "
                   "ways to look at the result."))

    f += H(5, "Tools, and why each one")
    f.append(table([
        ["Tool", "Job in NetMind", "Tool", "Job in NetMind"],
        ["Python", "the whole application", "SQLite", "stores every run, one file"],
        ["Scapy + Npcap", "live capture, pcap files", "Streamlit + Plotly", "the web dashboard and charts"],
        ["pandas, NumPy", "every table and the maths", "FastAPI", "REST API with docs at /docs"],
        ["scikit-learn", "Isolation Forest; TF-IDF", "NS2 + TCL + NAM", "the simulation and its animation"],
        ["NetworkX", "graph and shortest paths", "pytest", "automated tests, every page"],
    ], [0.17, 0.33, 0.19, 0.31]))
    f.append(Spacer(1, 4))
    f.append(P("Nothing needs internet or an API key for the demo; Claude or Ollama are optional Copilot backends.", "soft"))

    f += H(6, "The numbers to remember")
    f.append(tiles([("3 / 3", "injected problems found, right time and source"),
                    ("&lt; 0.5%", "false alarms: 3 of ~1,350 normal windows"),
                    ("5 / 5", "NS2 checks passed, twice"),
                    ("−31%", "delay with RED vs DropTail"),
                    ("82.4", "demo health score (normal 99.5)")]))
    f.append(table([
        ["Event (synthetic demo, 180 s)", "Time", "Evidence"],
        ["Congestion", "70–100 s", "latency 146 ms vs 26.5 normal; loss 9.5% vs 0"],
        ["Port scan from 192.168.1.66", "120–128 s", "311 destination ports per window vs ~10; 1,000 refused connections"],
        ["Ping flood from 192.168.1.66", "150–158 s", "551 packets/s vs 41, small ICMP packets"],
        ["NS2 (real run)", "3–6 s, 7 s", "delay 43.0 → 103.1 ms, 0 → 21 drops; rerouted via n4 at 115.2 ms"],
        ["RED vs DropTail (real run)", "3–6 s", "71.3 vs 103.1 ms delay; 25 vs 21 drops"],
    ], [0.3, 0.14, 0.56], head=INK))
    f.append(Spacer(1, 4))
    f.append(P("Always say the demo is <b>synthetic</b> traffic generated by NetMind, and the NS2 numbers are from the "
               "<b>real NS2 run</b> on Ubuntu 24.04.", "soft"))

    f += H(7, "Who presents what")
    chips = []
    owner = {1: "Affan", 2: "Affan", 3: "Hardik", 4: "Hardik", 5: "Affan", 6: "Affan", 7: "Affan", 8: "Hardik",
             9: "Affan", 10: "Hardik", 11: "Affan", 12: "Affan", 13: "Affan", 14: "Hardik", 15: "Both",
             16: "Hardik", 17: "Hardik", 18: "Both"}
    names = {1: "Cover", 2: "Problem", 3: "Goals", 4: "Design", 5: "Measure", 6: "Detect",
             7: "Results", 8: "Insights", 9: "Copilot", 10: "Routing", 11: "NS2", 12: "NS2 run",
             13: "RED", 14: "UI", 15: "Demo", 16: "Testing", 17: "Limits", 18: "Q&amp;A"}
    for n in range(1, 19):
        col = BOTH if owner[n] == "Both" else PEOPLE[owner[n]]
        x = Table([[P(f'<font name="Body-Bold" color="#{col["c"].hexval()[2:]}">{n}</font>', "cell",
                      alignment=TA_CENTER)], [P(names[n], "small", alignment=TA_CENTER, textColor=INK)]],
                  colWidths=[W / 9 - 4])
        x.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), col["l"]), ("ROUNDEDCORNERS", [4, 4, 4, 4]),
                               ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        chips.append(x)
    grid = Table([chips[:9], chips[9:]], colWidths=[W / 9] * 9)
    grid.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                              ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    f.append(grid)
    f.append(Spacer(1, 4))
    a, h = PEOPLE["Affan"]["c"].hexval()[2:], PEOPLE["Hardik"]["c"].hexval()[2:]
    f.append(P(f'<font color="#{a}"><b>Affan</b></font>: 9 slides, the pitch, measurement, detection, results, '
               f'Copilot and NS2. <font color="#{h}"><b>Hardik</b></font>: 7 slides plus the dashboard, objectives, '
               f'architecture, insights, routing, testing and limits. <b>Shared</b>: the demo and Q&amp;A.', "body"))
    f.append(table([
        ["Demo segment", "Who", "Shows the same topics as"],
        ["0:00–2:15  Overview, Hosts &amp; services, Topology &amp; routing", "Hardik", "his slides 8, 10, 14"],
        ["2:15–5:00  Incidents + Copilot, then NS2 checks and RED", "Affan", "his slides 6, 7, 9, 11–13"],
    ], [0.56, 0.14, 0.30], head=INK))
    f.append(short("each of you demonstrates exactly what you presented, so one person never explains the "
                   "other's slide."))

    f += H(8, "Questions either of you may get")
    qa = [("Networks or AI project?", "Networks first: capture, protocol analysis, RTT/loss/jitter, flows, topology, "
                                      "routing and NS2 are the core. ML and the Copilot interpret."),
          ("Why synthetic data?", "So the truth is known: we inject problems at known times and check NetMind finds "
                                  "them. Real captures and NS2 traces use the same pipeline."),
          ("What changed since Review 1?", "NS2 added and run (5/5 checks, plus RED), full implementation, "
                                           "redesigned dashboard, traffic insights, tests."),
          ("What is a flow?", "Packets with the same 5-tuple (source and destination IP and port, protocol), "
                              "both directions merged."),
          ("Why Isolation Forest?", "Unsupervised: no labelled attacks needed; unusual windows are isolated in "
                                    "fewer random splits."),
          ("What does NS2 add?", "Problems at known times in a repeatable network, and real Distance Vector "
                                 "rerouting."),
          ("What if the LLM is wrong?", "Numbers come from the database, not the model; it cites sources, only "
                                        "advises, and offline mode is deterministic."),
          ("Limitations?", "Tuned on synthetic traffic; topology is logical; passive loss is an estimate; HTTPS "
                           "content is encrypted.")]
    f.append(table([["Question", "Short answer"]] + [[f"<b>{q}</b>", a_] for q, a_ in qa], [0.27, 0.73]))

    f += H(9, "Review-day checklist")
    f += bullets([
        "Day before: <font face='Mono' size='8.4'>git pull</font>, <font face='Mono' size='8.4'>python -m pytest -q</font> "
        "(put the number on slide 16), open every dashboard page you will show, run the NS2 checks once.",
        "Rehearse together with the handover lines (in the speaker notes), then the demo with a timer.",
        "30 minutes before: two PowerShell windows (commands; dashboard running), Ubuntu at "
        "<font face='Mono' size='8.4'>~/netmind_ns2</font>, deck on slide 1, notifications off.",
        "Each of you reads your own Part B again; both re-read section 6 of Part A."])
    return f


# ================================================================ PART B, Affan
def part_affan():
    c = PEOPLE["Affan"]["c"]
    f = [PageBreak(), PartBanner("Part B, Affan", "Your slides, your demo, your questions",
                                 "Slides 1, 2, 5, 6, 7, 9, 11, 12, 13; demo 2:15–5:00. Hardik covers the rest.", c),
         Spacer(1, 6)]
    f += slide(1, "Cover", "Affan", "The 30-second pitch from Part A, then: “The line on this slide is real NetMind "
               "output: packets per second over our demo, with the three problems it found in red.”",
               ["Learn the pitch word for word; it is also the answer to “what is your project?”.",
                "Introduce Hardik and say he will cover objectives and architecture next."])
    f += slide(2, "The problem", "Affan", "“Latency 146 ms, loss 9.5%, 311 ports in two seconds. Each needs an "
               "expert to interpret. Is it congestion, an attack or a failed link? NetMind answers that, with the "
               "evidence.” Hand over: “Hardik will take you through what we set out to do and how it is built.”",
               ["All three numbers are from our synthetic demo: congestion, port scan, and the scan again."])
    f += slide(5, "Measurement (M4)", "Affan", "“We never send probes. Latency comes from request and reply pairs "
               "already in the traffic, loss is inferred from retransmissions and unanswered pings, and jitter is "
               "computed per path.”",
               ["<b>Latency</b>, <font face='Mono' size='8.4'>rtt_samples()</font>: TCP SYN → SYN-ACK with "
                "ack = seq + 1; ICMP echo request (type 8) → reply (type 0) with the same id and sequence; DNS "
                "query → response with the same transaction id. Typical: ping 3 ms, handshake 45 ms, DNS 29 ms.",
                "Averaged <b>per path</b> (client, server, type): mixing a 3 ms ping with a 45 ms handshake made "
                "jitter look like 20 ms on a calm network.",
                "<b>Loss</b> = (retransmissions + unanswered pings) ÷ (TCP data segments + pings). A "
                "retransmission = same direction, ports and sequence number seen twice.",
                "<b>Jitter</b> = mean |RTT now − RTT before| on one path. <b>Throughput</b> = bytes × 8 ÷ window.",
                "All of it per 2 s window: <font face='Mono' size='8.4'>window_metrics(df, window=2.0)</font>."],
               [("How can you see loss passively?", "You can't see the lost packet; you see TCP resend it, or a ping "
                                                    "with no reply. In NS2 drops are logged directly as d events.")])
    f += slide(6, "Detection (M3)", "Affan", "“Each 2-second window becomes ten features. An Isolation Forest and a "
               "robust z-score compare it with the normal baseline. The forest alone missed congestion, because loss "
               "is always zero when traffic is normal.”",
               ["<b>10 features</b>: packets/s, average packet size, connections, connection duration, distinct "
                "destination ports, TCP/UDP ratio, bytes/s, latency, loss, retransmissions.",
                "<b>Baseline</b>: the first 60 s of the demo (default: first 30%, at least 8 windows = 16 s). Less "
                "than that: “not enough traffic to judge”, never “normal”.",
                "<b>Isolation Forest</b> (200 trees): random splits isolate an unusual window in few steps. Score "
                "2^(−E[h(x)]/c(n)): ~0.5 normal, near 1 unusual. Threshold = 99th percentile of the baseline + 0.03 "
                "+ 0.25/√n.",
                "<b>z-score</b> = (value − baseline median) ÷ (1.4826 × MAD). Robust: medians ignore odd values.",
                "<b>Rule</b>: flag if z ≥ 6, or forest above threshold and z ≥ 4. Consecutive flags = one "
                "<b>incident</b>, typed by its strongest feature (ports → scan; latency/loss → congestion; "
                "packets/s with small packets → flood)."],
               [("Why both?", "The forest can't split on a feature that never varied in training (loss = 0). The "
                              "z-score catches it and names the feature."),
                ("How did you cut false alarms?", "z ≥ 4 behind a forest flag, stricter threshold for short "
                                                  "baselines, 16 s minimum: 18 → 3 of ~1,350 windows.")],
               extra=[code("is_anomaly = ((score > threshold) & (z >= 4)) | (z >= 6)")])
    f += slide(7, "Results", "Affan", "“All three injected problems found with the right time and source, and only "
               "3 of about 1,350 normal windows flagged.” Hand over: “Hardik will show what else we learn from the "
               "same traffic.”",
               ["Use the table in Part A section 6. Say clearly it is synthetic traffic.",
                "23 of the 90 windows were flagged, all inside the three events."])
    f += slide(9, "Copilot (M7, M8)", "Affan", "“The Copilot uses RAG: it retrieves the most relevant networking "
               "notes, adds the measured data and the incidents, and answers with citations. It runs offline by "
               "default and only advises.” Hand over: “Hardik will cover routing.”",
               ["<b>Knowledge base</b>: 9 notes we wrote (TCP, UDP/ICMP, DNS/HTTP, IP/OSI, routing, performance, "
                "congestion, attacks, NetMind), split into ~140-word chunks.",
                "<b>Retrieval</b>: TF-IDF vectors (offline, no download) and cosine similarity; top 4 chunks. "
                "Sentence Transformers and FAISS are used if installed.",
                "<b>Prompt</b> = question + network state (metrics, baseline, health, connections, DNS) + incidents "
                "with evidence + knowledge [1]–[4]. <font face='Mono' size='8.4'>ask --show-prompt</font> prints it.",
                "<b>Backends</b>: offline rule-based (default, used in tests), Claude API if a key is set, Ollama "
                "locally; falls back to offline if one fails."],
               [("What is RAG?", "Retrieval-Augmented Generation: fetch relevant text first, answer from it, cite it.")])
    f += slide(11, "NS2 scenario", "Affan", "“Five nodes: a TCP source, a UDP source, a router, a sink and a backup "
               "router. The n2–n3 link is a 1 Mb bottleneck with a 10-packet queue. A UDP burst at 3 s causes "
               "congestion; the main link fails at 7 s and Distance Vector reroutes through n4.”",
               ["Links: access 2 Mb/10 ms; bottleneck n2–n3 1 Mb/20 ms; backup n2–n4–n3 1 Mb/40 ms, cost 3 per "
                "link, so it is used only when n2–n3 is down. <font face='Mono' size='8.4'>$ns rtproto DV</font>.",
                "TCP window limited to 6: with NS2's default 20, TCP alone overflowed the queue before the burst.",
                "Trace line: <font face='Mono' size='8.4'>+ 0.5 0 2 tcp 1040 ------- 1 0.0 3.0 0 0</font> = event "
                "(+ enqueue, − dequeue, r receive, d drop), time, from, to, type, size, flags, flow, src, dst, "
                "seq, id.",
                "Definitions: delay = receive − send (one-way); loss = dropped ÷ (delivered + dropped)."],
               extra=[code("$ns duplex-link $n2 $n3 1Mb 20ms $qtype   ;# DropTail or RED\n"
                           "$ns queue-limit $n2 $n3 10\n"
                           "$ns at 3.0 \"$cbr start\"                  ;# 0.9 Mb/s UDP burst\n"
                           "$ns rtmodel-at 7.0 down $n2 $n3          ;# link failure\n"
                           "$ns rtmodel-at 8.5 up $n2 $n3")])
    f += slide(12, "NS2 results", "Affan", "“We ran it in NS2 twice and got identical results: five of five checks. "
               "Delay rose from 43 to 103 milliseconds, 21 packets dropped, and TCP took the path through n4.”",
               ["The five checks (check_trace.py): no drops 0.5–3 s; drops 3–6 s; delay higher in the burst; "
                "traffic via n4 during 7–8.5 s; TCP delay higher on the backup path (115.2 ms).",
                "check_trace.py uses only Python's standard library, so it runs on any lab machine."])
    f += slide(13, "DropTail vs RED", "Affan", "“RED drops early, at random, so the queue stays short: delay was "
               "71 instead of 103 milliseconds during the burst, at the cost of a few more drops.” Hand over: "
               "“Hardik will show it all in the dashboard.”",
               ["DropTail drops only when the queue is full. RED starts dropping once the <i>average</i> queue "
                "passes 3 packets, more often as it grows, so TCP backs off earlier.",
                "Burst: 71.3 vs 103.1 ms (−31%); 25 vs 21 drops; TCP goodput 0.150 vs 0.153 Mb/s. Normal and "
                "link-failure phases identical.",
                "Run: <font face='Mono' size='8.4'>ns netmind_scenario.tcl red RED</font> then "
                "<font face='Mono' size='8.4'>python3 compare_traces.py netmind.tr red.tr</font>."])

    f += H("D", "Your demo segment, 2:15–5:00", c)
    f.append(table([
        ["Time", "Do", "Point out"],
        ["2:15", "Dashboard → Incidents page", "port-scan card: 311 ports vs 10, source 192.168.1.66"],
        ["2:45", "Overview → Copilot panel: “Is anyone attacking my network?”", "names the scan, time, evidence; cites a note"],
        ["3:15", "Ubuntu: ns netmind_scenario.tcl, then python3 check_trace.py netmind.tr", "timeline prints; 5 × PASS"],
        ["4:15", "Ubuntu: ns netmind_scenario.tcl red RED, then python3 compare_traces.py netmind.tr red.tr", "RED 71.3 vs 103.1 ms"],
    ], [0.09, 0.5, 0.41], head=c))
    f.append(Spacer(1, 4))
    f.append(P("Ubuntu misbehaving? Dashboard → <b>NS2 lab</b> → Check a trace: upload netmind.tr (5 of 5), then both "
               "traces under DropTail vs RED. Copy them first with "
               "<font face='Mono' size='8.4'>cp ~/netmind_ns2/*.tr /mnt/c/Users/moham/Downloads/</font>.", "soft"))
    f.append(short("you show detection, the Copilot and NS2, the same things your slides explained.", c,
                   PEOPLE["Affan"]["l"]))
    f += H("Q", "Questions you lead", c)
    qa = [("How do you measure latency without sending anything?", "Request–reply pairs in the traffic: SYN→SYN-ACK, ping, DNS."),
          ("What is jitter, and why per path?", "Delay variation; different paths have different base delays."),
          ("What is the anomaly score?", "2^(−average path length / c(n)), 0–1; ~0.5 normal, near 1 unusual."),
          ("Why the median and MAD?", "One odd baseline value can't distort them, unlike the mean and standard deviation."),
          ("Why limit the TCP window to 6?", "With 20, TCP alone filled the 10-packet queue: no clean normal period."),
          ("What do + − r d mean in a trace?", "Enqueue, dequeue, receive, drop."),
          ("Why TF-IDF and not only embeddings?", "Works offline with no download; embeddings can be switched on.")]
    f.append(table([["Question", "Answer"]] + [[f"<b>{q}</b>", a_] for q, a_ in qa], [0.42, 0.58], head=c))
    f.append(Spacer(1, 6))
    f.append(P("Backup for Hardik's topics: know Part A sections 3–5 well enough to answer what a flow is, what the "
               "health score means and how Distance Vector differs from Link State.", "soft"))
    return f


# ================================================================ PART B, Hardik
def part_hardik():
    c = PEOPLE["Hardik"]["c"]
    f = [PageBreak(), PartBanner("Part B, Hardik", "Your slides, your demo, your questions",
                                 "Slides 3, 4, 8, 10, 14, 16, 17; demo 0:00–2:15. Affan covers the rest.", c),
         Spacer(1, 6)]
    f += slide(3, "Objectives", "Hardik", "“We set five objectives: measure the network from its traffic, detect "
               "unusual behaviour, explain it in plain language, compare routing algorithms, and simulate problems in "
               "NS2, which we added after Review 1 as suggested.”",
               ["Use the five words: Measure, Detect, Explain, Route, Simulate."])
    f += slide(4, "Architecture", "Hardik", "“Four inputs become one packet table, so one pipeline analyses them all. "
               "Results are saved as a run in SQLite and read by the dashboard, the API, the command line and the "
               "Copilot. I built capture, the traffic analyzer, topology, storage and the dashboard; Affan built "
               "performance, detection, the knowledge base, the Copilot and NS2.” Hand over: “Affan will now explain "
               "how the measuring and detection work.”",
               ["<b>The packet record</b> (records.py): ts, src, dst, sport, dport, proto, app, length, payload_len, "
                "tcp_flags, seq, ack, icmp_type/id/seq, dns_id/qr/qname. Every module uses only this table.",
                "<b>Inputs</b>: sniffer.py (Scapy <font face='Mono' size='8.4'>sniff</font> / "
                "<font face='Mono' size='8.4'>rdpcap</font>), ns2.py (trace lines), synthetic.py (3 clients, DNS, "
                "web, pings; congestion 70–100 s, scan 120–128 s, flood 150–158 s; seed 7).",
                "<b>pipeline.py</b>, <font face='Mono' size='8.4'>analyze_packets()</font>: summary → metrics → "
                "features → detection → incidents → topology → insights → health → save.",
                "<b>db.py</b>: SQLite <font face='Mono' size='8.4'>data/netmind.db</font>; a runs table plus metrics, "
                "anomalies, incidents, flows, protocols, rtt, nodes, links, hosts, connections, dns, all with run_id."],
               [("Why one table for every input?", "So no module depends on where packets came from; a pcap, NS2 "
                                                    "trace or the demo go through the same code.")])
    f += slide(8, "Traffic insights", "Hardik", "“We follow every TCP connection from its SYN. That finds the port scan "
               "without any machine learning: 1,000 refused attempts from one host to 1,000 ports. The health score "
               "is 82.4 for the demo and 99.5 for normal traffic.” Hand over: “Affan will explain how the Copilot "
               "turns this into answers.”",
               ["<b>Connections</b> (insights.py): established = SYN-ACK came back; refused = RST; unanswered = "
                "nothing; reset = SYN-ACK then RST. Handshake time = SYN-ACK − SYN (median 45.7 ms).",
                "<b>Likely scanner</b>: ≥ 20 failed attempts to ≥ 20 different ports. Demo: 192.168.1.66.",
                "<b>DNS</b>: query matched to response by transaction id: 364 lookups, 4 unanswered, median 29.3 ms.",
                "<b>Hosts</b>: 9; scope from the address (private/public); role from behaviour (3 clients, "
                "5 servers, 1 likely scanner); services it answered (TCP 443, DNS 53, ICMP echo).",
                "<b>Health</b>: 100 − up to 40 (latency vs normal, all 40 at 4×) − up to 40 (loss, all 40 at 5%) − 20 "
                "(if flagged); averaged. 90+ Good, 70–90 Fair, &lt; 70 Poor."],
               [("What does a refused connection mean?", "The host is up but the port is closed: it answered RST.")])
    f += slide(10, "Routing (M5)", "Hardik", "“Hosts that talked form a graph. Dijkstra gives the shortest path; Link "
               "State is the OSPF idea, Distance Vector the RIP idea. They give the same costs, and when a link fails "
               "Distance Vector recomputes.” Hand over: “Affan will show the same routing in NS2.”",
               ["<b>Graph</b> (graph.py, NetworkX): nodes = hosts; edges = hosts that exchanged packets; costs = "
                "median measured RTT, or hops = 1. Logical, not physical cabling.",
                "<b>Dijkstra</b>: take the closest unfinished node each step; needs non-negative costs.",
                "<b>Link State</b> (OSPF): every node knows the whole map and runs Dijkstra itself.",
                "<b>Distance Vector</b> (RIP): each round every node shares its table with neighbours and updates "
                "cost(d) = min over neighbours n of link(u, n) + cost_n(d) until nothing changes (Bellman-Ford).",
                "Tests: LS and DV give identical costs; DV reroutes when a link is removed."],
               [("Dijkstra vs Bellman-Ford?", "Bellman-Ford relaxes all edges repeatedly and handles negative "
                                              "costs; it is the basis of DV."),
                ("Drawback of DV?", "Slower convergence; can count to infinity.")])
    f += slide(14, "Dashboard (M9)", "Hardik", "“The dashboard has ten pages. We'll show the Overview, Hosts and "
               "services, Topology and routing, and Affan will show the NS2 lab.”",
               ["Pages: Overview, Incidents, Traffic, Hosts &amp; services, Performance, Topology &amp; routing, "
                "NS2 lab, Copilot, Compare runs, Data &amp; export.",
                "Files: app.py (pages), charts.py (Plotly), logic.py (cards, severity, reports, link-failure "
                "simulation; testable without a browser), ns2lab.py, theme.py (light and dark).",
                "Sidebar → Start a new run: demo (seed, length), normal-only traffic, upload a pcap or NS2 trace, "
                "live capture. Start with <font face='Mono' size='8.4'>python -m netmind dashboard</font> → "
                "localhost:8501."])
    f += slide(16, "Testing", "Hardik", "“Three of three problems found, under half a percent false alarms, five of "
               "five NS2 checks, and an automated test suite that covers every module and every dashboard page.”",
               ["Say the pytest result from the laptop (<font face='Mono' size='8.4'>python -m pytest -q</font>).",
                "Tests need no network, admin rights, NS2 or API key; the Copilot is forced offline.",
                "False alarms: 5 capture lengths × 10 seeds of normal-only traffic, ~1,350 windows, 3 flagged."])
    f += slide(17, "Limitations and next steps", "Hardik", "“Our thresholds were tuned on synthetic data, the topology "
               "is logical, and passive loss is an estimate. Next: real campus captures, bigger NS2 scenarios and "
               "continuous monitoring.”",
               ["Also: HTTPS payloads are encrypted, so only headers, sizes and timing are used."])

    f += H("D", "Your demo segment, 0:00–2:15", c)
    f.append(table([
        ["Time", "Do", "Point out"],
        ["0:00", "Dashboard → Overview (newest run)", "red bands = incidents; health badge 82.4 Fair; headline numbers"],
        ["0:45", "Hosts &amp; services", "warning: 192.168.1.66, 1,000 refused attempts to 1,000 ports; 9 hosts and roles"],
        ["1:30", "Topology &amp; routing: From 192.168.1.10 To 8.8.8.8, then Simulate a link failure",
         "Dijkstra path; LS vs DV table; which routes changed and DV rounds"],
        ["2:15", "Hand over", "“Affan will show what the detector and the Copilot make of this, and NS2.”"],
    ], [0.09, 0.46, 0.45], head=c))
    f.append(Spacer(1, 4))
    f.append(P("Set-up is yours: PowerShell 2 runs <font face='Mono' size='8.4'>python -m netmind dashboard</font> "
               "before the panel arrives, with the newest demo run selected.", "soft"))
    f.append(short("you show the dashboard, the hosts and the routing, the same things your slides explained.", c,
                   PEOPLE["Hardik"]["l"]))
    f += H("Q", "Questions you lead", c)
    qa = [("What is the three-way handshake?", "SYN, SYN-ACK, ACK. We time SYN→SYN-ACK and use the reply for the outcome."),
          ("How else do you detect a port scan?", "Many refused attempts from one host to many ports, no ML needed."),
          ("How is a host's role decided?", "From behaviour: answered connections/DNS/pings = server; started them = client."),
          ("Link State vs Distance Vector?", "LS: whole map + Dijkstra (OSPF). DV: tables with neighbours only (RIP)."),
          ("Why SQLite?", "No server to install; one file holds every run."),
          ("Why Streamlit?", "A web dashboard written in Python, no HTML or JavaScript needed."),
          ("What does the health score mean?", "How much the users felt the problem, in one number; incidents say what it was.")]
    f.append(table([["Question", "Answer"]] + [[f"<b>{q}</b>", a_] for q, a_ in qa], [0.42, 0.58], head=c))
    f.append(Spacer(1, 6))
    f.append(P("Backup for Affan's topics: know Part A sections 2, 3 and 6 well enough to explain the Isolation "
               "Forest in one sentence, what RAG is, and the NS2 and RED numbers.", "soft"))
    return f


# ================================================================ pages
def make(person: str, out: Path):
    p = PEOPLE[person]

    def cover(cv, doc):
        cv.saveState()
        h = A4[1]
        cv.setFillColor(NIGHT)
        cv.rect(0, h - 118 * mm, A4[0], 118 * mm, stroke=0, fill=1)
        cv.setFillColor(CYAN)
        cv.setFont("Body-Semi", 10)
        cv.drawString(18 * mm, h - 24 * mm, "COMPUTER NETWORKS LAB (BCSE308P), REVIEW 2")
        cv.setFillColor(colors.HexColor("#F2F6F7"))
        cv.setFont("Body-Bold", 40)
        cv.drawString(18 * mm, h - 44 * mm, "NetMind")
        cv.setFont("Body", 13)
        cv.setFillColor(colors.HexColor("#BFD3D6"))
        cv.drawString(18 * mm, h - 53 * mm, "AI-Powered Network Intelligence and LLM Network Copilot")
        # the demo's packets/s trace with the incident bands
        x0, y0, wd, ht = 18 * mm, h - 96 * mm, A4[0] - 36 * mm, 30 * mm
        cv.setFillColor(colors.HexColor("#3A2629"))
        for a, b in ((70, 100), (120, 128), (150, 158)):
            cv.rect(x0 + wd * a / 180, y0, wd * (b - a) / 180, ht, stroke=0, fill=1)
        pts = [0, 197, 18, 198, 37, 194, 55, 196, 74, 195, 92, 196, 111, 198, 129, 195, 148, 201, 166, 195,
               185, 197, 203, 197, 222, 199, 240, 198, 259, 194, 277, 196, 296, 201, 314, 195, 333, 198, 351, 195,
               370, 200, 388, 194, 407, 201, 425, 198, 444, 199, 462, 200, 481, 196, 499, 198, 518, 199, 536, 195,
               555, 202, 573, 199, 592, 192, 610, 198, 629, 198, 647, 200, 666, 197, 684, 198, 703, 198, 721, 196,
               740, 197, 758, 200, 777, 198, 795, 199, 814, 195, 832, 194, 850, 198, 869, 196, 887, 199, 906, 202,
               924, 198, 943, 197, 961, 196, 980, 199, 998, 198, 1017, 195, 1035, 201, 1054, 198, 1072, 194,
               1091, 200, 1109, 112, 1128, 104, 1146, 108, 1165, 112, 1183, 203, 1202, 189, 1220, 196, 1239, 196,
               1257, 196, 1276, 196, 1294, 194, 1313, 192, 1331, 198, 1350, 197, 1368, 192, 1387, 22, 1405, 16,
               1424, 18, 1442, 24, 1461, 192, 1479, 200, 1498, 196, 1516, 193, 1535, 197, 1553, 201, 1572, 200,
               1590, 199, 1609, 198, 1627, 198, 1646, 196]
        cv.setStrokeColor(CYAN)
        cv.setLineWidth(1.6)
        path = cv.beginPath()
        for i in range(0, len(pts), 2):
            x, y = x0 + pts[i] / 1664 * wd, y0 + (220 - pts[i + 1]) / 220 * ht
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        cv.drawPath(path, stroke=1, fill=0)
        cv.setFont("Body", 8)
        cv.setFillColor(colors.HexColor("#8FA6AD"))
        cv.drawString(x0, y0 - 5 * mm, "Packets per second across the synthetic demo; red bands are the three incidents NetMind found.")
        # who this copy is for
        cv.setFillColor(p["c"])
        cv.roundRect(18 * mm, h - 132 * mm, cv.stringWidth(f"Study notes for {p['full']} ({p['reg']})", "Body-Semi", 11) + 9 * mm, 11 * mm, 5, stroke=0, fill=1)
        cv.setFillColor(colors.white)
        cv.setFont("Body-Semi", 11)
        cv.drawString(22 * mm, h - 128.2 * mm, f"Study notes for {p['full']} ({p['reg']})")
        cv.restoreState()
        footer(cv, doc)

    def footer(cv, doc):
        cv.saveState()
        cv.setFont("Body", 7.5)
        cv.setFillColor(MUTED)
        cv.drawString(18 * mm, 10 * mm, "NetMind, Review 2 study notes")
        cv.setFillColor(p["c"])
        cv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{p['full']}  |  page {doc.page}")
        cv.setStrokeColor(LINE)
        cv.setLineWidth(0.5)
        cv.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
        cv.restoreState()

    story = [Spacer(1, 128 * mm),
             P("<b>How to use these notes.</b> Part A is the same in both copies: the essentials either of us can "
               "be asked about. Part B is only your slides, your part of the demo and the questions you lead. "
               "Read Part A twice and Part B until you can say it without looking.", "body"),
             Spacer(1, 4)]
    story += part_a()
    story += part_affan() if person == "Affan" else part_hardik()
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=20 * mm, title=f"NetMind Review 2 notes, {p['full']}",
                            author="Mohammed Affan, Hardik")
    doc.build(story, onFirstPage=cover, onLaterPages=footer)
    return out


if __name__ == "__main__":
    outdir = Path(os.environ.get("NETMIND_NOTES_OUT", HERE))
    for who, name in (("Affan", "NetMind_Review2_Notes_Affan.pdf"), ("Hardik", "NetMind_Review2_Notes_Hardik.pdf")):
        print(make(who, outdir / name))
