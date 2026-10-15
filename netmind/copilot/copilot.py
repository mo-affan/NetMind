"""M8 LLM Network Copilot.

The Copilot answers questions about the network by combining four inputs into one prompt:
  1. the user's question
  2. the current network statistics (from the database)
  3. the anomaly results (incidents found by the ML module)
  4. networking knowledge retrieved by the RAG engine

LLM backends (chosen automatically, or set NETMIND_LLM=anthropic|ollama|offline):
  anthropic  Claude via the Anthropic API. Needs ANTHROPIC_API_KEY.
             Model from NETMIND_LLM_MODEL (default claude-haiku-5-5).
  ollama     A local open model via Ollama (https://ollama.com), free and offline.
             Model from NETMIND_OLLAMA_MODEL (default llama3.2).
  offline    No LLM: a rule-based explanation built from the same evidence and
             knowledge. Always available, so the demo works without an API key.

The Copilot is advisory only. It never changes, blocks or configures anything.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from netmind.rag import KnowledgeBase

SYSTEM_PROMPT = """You are NetMind Copilot, a network troubleshooting assistant for a \
Computer Networks lab project.
Rules:
- Base every statement about this network on the NETWORK STATE and INCIDENTS given. Quote \
the numbers. If the data does not show something, say so; do not invent measurements.
- Use the KNOWLEDGE excerpts for explanations and cite them as [1], [2].
- Structure: a one-line answer, then the evidence, then the likely cause, then 2-4 concrete \
checks the user can do.
- You are advisory only: recommend, never claim to have changed the network.
- Be concise (under 220 words) and use plain language a student can follow."""

ACTIONS = {
    "congestion": ["Find the busiest flows and top talkers during the incident window.",
                   "Check utilization of the bottleneck link; near 100% confirms saturation.",
                   "Look for UDP streams that keep sending while TCP flows slow down.",
                   "Rate-limit or reschedule bulk transfers, or apply QoS to interactive traffic."],
    "port_scan": ["Check whether {src} is an authorised scanner; if not, block it at the firewall.",
                  "Review which ports on {dst} are actually open and close unneeded services.",
                  "Watch for follow-up connections from {src} to the ports that answered."],
    "flood": ["Rate-limit or block {proto} traffic from {src} at the gateway or firewall.",
              "Check {dst}'s CPU and link load during the flood.",
              "Confirm the source address is not spoofed before blocking a whole range."],
    "traffic_spike": ["Identify the application behind the spike (top flows by bytes).",
                      "Decide whether it is expected (backup, update) or should be rate-limited."],
    "unusual": ["Compare the flagged features with normal values and inspect the top flows."],
    "reroute": ["Find out why the primary link failed and restore it.",
                "Expect higher latency while traffic uses the backup path."],
}

TOPIC_WORDS = {
    "congestion": ["slow", "slowdown", "latency", "delay", "lag", "loss", "drop", "congest",
                   "retrans", "jitter", "throughput", "speed", "performance"],
    "port_scan": ["scan", "port", "probe", "attack", "intrus", "security", "suspicious"],
    "flood": ["flood", "ping", "icmp", "dos", "ddos", "attack", "spike", "burst"],
    "reroute": ["route", "routing", "link", "fail", "path", "reroute", "down"],
}


def _fmt_feature(f: dict) -> str:
    names = {"pps": "packets/s", "avg_pkt_size": "avg packet size (B)", "connections": "connections",
             "avg_conn_duration": "connection duration (s)", "dst_ports": "distinct dest ports",
             "tcp_udp_ratio": "TCP/UDP ratio", "bytes_per_sec": "bytes/s",
             "latency_ms": "latency (ms)", "loss_pct": "loss (%)", "retransmissions": "TCP retransmissions"}
    return f"{names.get(f['feature'], f['feature'])} {f['value']:g} vs normal {f['normal']:g}"


def state_to_text(state: dict) -> str:
    """Compact text version of the network state for the prompt."""
    lines = []
    run = state.get("run", {})
    lines.append(f"Run: {run.get('name', '?')} (source: {run.get('source', '?')})")
    s = state.get("summary", {})
    if s:
        lines.append(f"Traffic: {s.get('packets')} packets, {s.get('bytes')} bytes over "
                     f"{s.get('duration_s')} s, {s.get('hosts')} hosts, {s.get('flows')} flows; "
                     f"protocols {s.get('protocols')}")
    o = state.get("overall", {})
    if o:
        lines.append("Whole capture: " + ", ".join(f"{k}={v}" for k, v in o.items() if v is not None))
    b = state.get("baseline", {})
    if b:
        lines.append("Normal (baseline) values: " + ", ".join(f"{k}={round(v, 2)}" for k, v in b.items()))
    cur = state.get("latest_window")
    if cur:
        lines.append("Latest window: " + ", ".join(f"{k}={v}" for k, v in cur.items()))
    for r in state.get("routes", []):
        lines.append(f"Route change at t={r['t']} s for flow {r['fid']}: {r['path']}")
    return "\n".join(lines)


def incidents_to_text(incidents: list[dict], status: dict | None = None) -> str:
    if status and status.get("state") == "insufficient_data":
        return ("Anomaly detection was NOT run: not enough traffic to learn a normal baseline ("
                f"{status.get('reason')}). Do not claim the network is normal or abnormal "
                "from anomaly results.")
    if not incidents:
        return "No anomalies detected: all windows look like normal traffic."
    out = []
    for i, e in enumerate(incidents, 1):
        feats = "; ".join(_fmt_feature(f) for f in e.get("top_features", []))
        out.append(f"{i}. {e['title']} from t={e['start_t']:g} s to {e['end_t']:g} s "
                   f"(peak anomaly score {e['peak_score']:.2f}, deviation {e['peak_deviation']:.0f}). "
                   f"Busiest: {e.get('top_proto')} from {e.get('top_src')} to {e.get('top_dst')}. "
                   f"Stand-out features: {feats}")
    return "\n".join(out)


def build_prompt(question: str, state: dict, docs: list[dict]) -> str:
    knowledge = "\n\n".join(f"[{i}] {d['title']}\n{d['text']}" for i, d in enumerate(docs, 1))
    return (f"QUESTION: {question}\n\nNETWORK STATE:\n{state_to_text(state)}\n\n"
            f"INCIDENTS:\n{incidents_to_text(state.get('incidents', []), state.get('anomaly_status'))}\n\n"
            f"KNOWLEDGE:\n{knowledge or '(none retrieved)'}")


# ---------------------------------------------------------------------------
# LLM backends
# ---------------------------------------------------------------------------
def _post(url: str, payload: dict, headers: dict, timeout: float = 60) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"content-type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def call_anthropic(system: str, prompt: str) -> str:
    key = os.environ["ANTHROPIC_API_KEY"]
    model = os.environ.get("NETMIND_LLM_MODEL", "claude-haiku-5-5")
    data = _post("https://api.anthropic.com/v1/messages",
                 {"model": model, "max_tokens": 700, "system": system,
                  "messages": [{"role": "user", "content": prompt}]},
                 {"x-api-key": key, "anthropic-version": "2023-06-01"})
    return "".join(b.get("text", "") for b in data.get("content", []))


def ollama_url() -> str:
    return os.environ.get("NETMIND_OLLAMA_URL", "http://localhost:11434")


def call_ollama(system: str, prompt: str) -> str:
    model = os.environ.get("NETMIND_OLLAMA_MODEL", "llama3.2")
    data = _post(f"{ollama_url()}/api/chat",
                 {"model": model, "stream": False,
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": prompt}]}, {}, timeout=180)
    return data.get("message", {}).get("content", "")


def ollama_available() -> bool:
    try:
        urllib.request.urlopen(f"{ollama_url()}/api/tags", timeout=1.5)
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def pick_backend() -> str:
    choice = os.environ.get("NETMIND_LLM", "auto").lower()
    if choice != "auto":
        return choice
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if ollama_available():
        return "ollama"
    return "offline"


# ---------------------------------------------------------------------------
# Offline (no-LLM) answer
# ---------------------------------------------------------------------------
CONCEPT_START = ("what is", "what are", "what's", "whats", "explain", "define", "how does",
                 "how do", "difference between", "why does tcp", "why do")
ABOUT_DATA = ("my ", "this ", "our ", "here", "capture", "right now", "currently", "network slow",
              "happening", "wrong", "causing", "today", "detected")


def is_concept_question(question: str) -> bool:
    """'What is jitter?' is about networking theory; 'why is my network slow?' is about the data."""
    q = question.lower().strip()
    return q.startswith(CONCEPT_START) and not any(w in q for w in ABOUT_DATA)


def _topics(question: str) -> set[str]:
    q = question.lower()
    return {t for t, words in TOPIC_WORDS.items() if any(w in q for w in words)}


def _first_sentences(text: str, n: int = 2) -> str:
    import re
    return " ".join(re.split(r"(?<=[.!?])\s+", text)[:n])


def offline_answer(question: str, state: dict, docs: list[dict]) -> str:
    incidents = state.get("incidents", [])
    routes = state.get("routes", [])
    topics = _topics(question)
    relevant = [e for e in incidents if not topics or e["type"] in topics
                or (e["type"] == "traffic_spike" and "flood" in topics)
                or (e["type"] == "reroute" and "congestion" in topics)]
    reroutes = [r for r in routes if r is not routes[0]] if routes else []
    cite = {d["source"]: i for i, d in enumerate(docs, 1)}

    def ref(*names):
        for n in names:
            if n in cite:
                return f" [{cite[n]}]"
        return ""

    parts = []
    if is_concept_question(question) and docs:
        parts.append(f"{_first_sentences(docs[0]['text'], 4)} [1]")
        if len(docs) > 1 and docs[1]["score"] > 0.15:
            parts.append(f"{_first_sentences(docs[1]['text'], 2)} [2]")
        o = state.get("overall", {})
        if o:
            parts.append("**In this capture:** " + ", ".join(
                f"{k.replace('_', ' ')} {v}" for k, v in o.items()
                if k in ("latency_ms", "jitter_ms", "loss_pct", "throughput_mbps") and v is not None) + ".")
        parts.append("Sources: " + "; ".join(f"[{i}] {d['title']}" for i, d in enumerate(docs, 1)))
        return "\n\n".join(parts)
    if relevant:
        e = max(relevant, key=lambda x: x["peak_deviation"])
        others = [x for x in relevant if x is not e]
        parts.append(f"**Most likely: {e['title'].lower()}** between t={e['start_t']:g} s and "
                     f"t={e['end_t']:g} s (anomaly score {e['peak_score']:.2f}).")
        parts.append("**Evidence:** " + "; ".join(_fmt_feature(f) for f in e["top_features"]) +
                     f". Busiest traffic in that period: {e['top_proto']} from {e['top_src']} "
                     f"to {e['top_dst']}.")
        why = {"congestion": "Latency, loss and retransmissions rising together is the classic sign of "
                             "congestion: router queues fill, packets wait longer and are then dropped, "
                             "so TCP retransmits and slows down" + ref("congestion.md", "tcp.md") + ".",
               "port_scan": f"One host ({e['top_src']}) contacting a very large number of distinct ports "
                            "with small SYN packets is the pattern of a port scan" + ref("security.md") + ".",
               "flood": f"Packet rate far above normal with small packets from {e['top_src']} is a flood; "
                        f"with {e['top_proto']} traffic this is most likely a ping flood"
                        + ref("udp_icmp.md", "security.md") + ".",
               "reroute": "Traffic switched to a longer path at the same time, which is what routing "
                          "does after a link fails; the backup path adds delay"
                          + ref("routing.md") + ".",
               "traffic_spike": "Traffic volume is far above normal, typical of a large transfer"
                                + ref("performance.md") + ".",
               "unusual": "The traffic differs from normal in the features above" + ref("netmind.md") + "."}
        parts.append("**Why:** " + why[e["type"]])
        acts = [a.format(src=e["top_src"], dst=e["top_dst"], proto=e["top_proto"])
                for a in ACTIONS[e["type"]]]
        parts.append("**What to check:**\n" + "\n".join(f"- {a}" for a in acts))
        if others:
            parts.append("Also detected: " + "; ".join(
                f"{x['title'].lower()} at t={x['start_t']:g}-{x['end_t']:g} s" for x in others) + ".")
    if reroutes and (not topics or "reroute" in topics or "congestion" in topics):
        r = reroutes[0]
        parts.append(f"**Route change:** at t={r['t']:.2f} s flow {r['fid']} switched to path "
                     f"{r['path']}, which suggests a link failure and rerouting"
                     + ref("routing.md") + ". " + ACTIONS["reroute"][1])
    if not parts:
        if incidents and topics:
            parts.append("Nothing related to that shows up in this capture. Detected incidents: " +
                         "; ".join(f"{x['title'].lower()} at t={x['start_t']:g} s" for x in incidents) + ".")
        elif not incidents:
            o = state.get("overall", {})
            measured = (f"Latency {o.get('latency_ms')} ms, loss {o.get('loss_pct')}%, "
                        f"throughput {o.get('throughput_mbps')} Mbps.")
            status = state.get("anomaly_status") or {}
            if status.get("state") == "insufficient_data":
                parts.append("**Not enough traffic to judge:** anomaly detection needs a normal "
                             f"baseline, and {status.get('reason')}. What was measured: " + measured)
            else:
                parts.append("**No anomalies detected:** every time window looks like normal "
                             "traffic. " + measured)
        if docs:
            parts.append(f"**Background:** {_first_sentences(docs[0]['text'], 3)} [1]")
    elif docs and not relevant and not reroutes:
        parts.append(f"**Background:** {_first_sentences(docs[0]['text'], 3)} [1]")
    if docs:
        parts.append("Sources: " + "; ".join(f"[{i}] {d['title']}" for i, d in enumerate(docs, 1)))
    parts.append("_NetMind Copilot is advisory: it explains and recommends, it does not change the network._")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
class Copilot:
    def __init__(self, kb: KnowledgeBase | None = None, backend: str | None = None, k: int = 4):
        self.kb = kb or KnowledgeBase.build(backend="tfidf")
        self.backend = backend or pick_backend()
        self.k = k

    def retrieve(self, question: str, state: dict) -> list[dict]:
        topics = _topics(question)
        if is_concept_question(question):
            return self.kb.search(question, self.k)
        extra = " ".join(e["title"] for e in state.get("incidents", [])
                         if not topics or e["type"] in topics)
        return self.kb.search(f"{question} {extra}".strip(), self.k)

    def ask(self, question: str, state: dict) -> dict:
        docs = self.retrieve(question, state)
        prompt = build_prompt(question, state, docs)
        used = self.backend
        try:
            if used == "anthropic":
                answer = call_anthropic(SYSTEM_PROMPT, prompt)
            elif used == "ollama":
                answer = call_ollama(SYSTEM_PROMPT, prompt)
            else:
                used, answer = "offline", offline_answer(question, state, docs)
        except (urllib.error.URLError, KeyError, OSError, ValueError) as err:
            used = f"offline (fallback: {self.backend} failed: {err.__class__.__name__})"
            answer = offline_answer(question, state, docs)
        return {"question": question, "answer": answer, "backend": used,
                "sources": [{"n": i, "title": d["title"], "score": d["score"]}
                            for i, d in enumerate(docs, 1)],
                "prompt": prompt}
