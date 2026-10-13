import pytest

from netmind.copilot import Copilot, build_prompt
from netmind.copilot.copilot import is_concept_question
from netmind.pipeline import analyze_packets, get_state
from netmind.rag import KnowledgeBase


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase.build(backend="tfidf")


@pytest.mark.parametrize("question,expected", [
    ("someone is scanning my ports", "Port scan"),
    ("why is jitter high", "Jitter"),
    ("how does distance vector routing work", "Distance Vector"),
    ("explain the tcp three way handshake", "Three-way handshake"),
])
def test_retrieval(kb, question, expected):
    assert expected in kb.search(question, 3)[0]["title"]


def test_concept_vs_data_questions():
    assert is_concept_question("What is jitter?")
    assert not is_concept_question("What is causing my network slowdown?")


def test_copilot_offline_answers_from_data(db, demo, kb):
    df, _ = demo
    rid = analyze_packets(df, "demo", "demo", db, train_until=60, save_model=False)
    state = get_state(db, rid)
    c = Copilot(kb, backend="offline")
    slow = c.ask("What is causing the network slowdown?", state)
    assert "congestion" in slow["answer"].lower() and "latency" in slow["answer"]
    attack = c.ask("Is someone attacking my network?", state)
    assert "port scan" in attack["answer"] and "192.168.1.66" in attack["answer"]
    assert slow["backend"] == "offline" and slow["sources"]


def test_prompt_contains_all_four_inputs(db, demo, kb):
    df, _ = demo
    rid = analyze_packets(df, "demo", "demo", db, train_until=60, save_model=False)
    state = get_state(db, rid)
    docs = kb.search("slow network", 2)
    p = build_prompt("Why slow?", state, docs)
    for part in ("QUESTION: Why slow?", "NETWORK STATE:", "INCIDENTS:", "KNOWLEDGE:", "[1]"):
        assert part in p


def test_falls_back_to_offline_when_llm_unreachable(db, demo, kb, monkeypatch):
    df, _ = demo
    rid = analyze_packets(df, "demo", "demo", db, train_until=60, save_model=False)
    monkeypatch.setenv("NETMIND_OLLAMA_URL", "http://127.0.0.1:9")
    res = Copilot(kb, backend="ollama").ask("why slow?", get_state(db, rid))
    assert res["backend"].startswith("offline (fallback")
