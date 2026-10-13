"""M8 LLM Network Copilot

Builds a prompt from the question, network state, anomaly incidents and RAG
knowledge, and answers with Claude (Anthropic API), a local Ollama model, or an
offline rule-based explanation. Advisory only.

Owner: Affan. Phase: 6.
"""
from .copilot import Copilot, build_prompt, offline_answer, pick_backend, SYSTEM_PROMPT

__all__ = ["Copilot", "build_prompt", "offline_answer", "pick_backend", "SYSTEM_PROMPT"]
