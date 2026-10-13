"""M7 RAG Knowledge Engine

Networking knowledge base (rag/knowledge/*.md), section-based chunking,
embeddings (TF-IDF offline by default, Sentence Transformers optional) and
cosine-similarity vector search (FAISS if installed, else NumPy).

Owner: Affan. Phase: 5.
"""
from .engine import KnowledgeBase, chunk_documents, load_documents, KNOWLEDGE_DIR

__all__ = ["KnowledgeBase", "chunk_documents", "load_documents", "KNOWLEDGE_DIR"]
