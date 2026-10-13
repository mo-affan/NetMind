"""M7 RAG Knowledge Engine.

Offline (once):  networking documents -> chunks -> embeddings -> vector index
At question time: question -> embedding -> top-k most similar chunks

Two embedding backends:
  "tfidf"     scikit-learn TF-IDF vectors. Works offline with no downloads (default).
  "sentence"  Sentence Transformers (all-MiniLM-L6-v2) for semantic embeddings, so
              "packets are being dropped" matches "packet loss". Needs
              `pip install sentence-transformers` and downloads the model once.
Vector search uses FAISS (inner product on normalised vectors) when installed,
otherwise an exact NumPy cosine-similarity search. Both give the same results.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


@dataclass
class Chunk:
    id: int
    source: str   # file name
    title: str    # "Document title > Section"
    text: str


def load_documents(folder: str | Path = KNOWLEDGE_DIR) -> list[tuple[str, str]]:
    """(file name, text) for every .md / .txt file in the folder."""
    folder = Path(folder)
    return [(p.name, p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*"))
            if p.suffix in (".md", ".txt")]


def chunk_documents(docs: list[tuple[str, str]], max_words: int = 140) -> list[Chunk]:
    """Split each document at its '## ' sections; long sections are split further by sentences."""
    chunks: list[Chunk] = []
    for name, text in docs:
        m = re.search(r"^# (.+)$", text, flags=re.M)
        doc_title = m.group(1).strip() if m else name
        sections = re.split(r"^## ", text, flags=re.M)
        for sec in sections[1:] if len(sections) > 1 else sections:
            lines = sec.strip().splitlines()
            head = lines[0].strip().lstrip("# ").strip() if len(sections) > 1 else doc_title
            body = " ".join(l.strip() for l in lines[1:] if l.strip()) if len(sections) > 1 \
                else " ".join(l.strip() for l in lines if l.strip() and not l.startswith("#"))
            sentences = re.split(r"(?<=[.!?])\s+", body)
            buf: list[str] = []
            for s in sentences:
                if buf and len(" ".join(buf + [s]).split()) > max_words:
                    chunks.append(Chunk(len(chunks), name, f"{doc_title} > {head}", " ".join(buf)))
                    buf = []
                buf.append(s)
            if buf:
                chunks.append(Chunk(len(chunks), name, f"{doc_title} > {head}", " ".join(buf)))
    return chunks


class TfidfEmbedder:
    name = "tfidf"

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english",
                                   min_df=1)

    def fit(self, texts: list[str]) -> "TfidfEmbedder":
        self.vec.fit(texts)
        return self

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.vec.transform(texts).toarray().astype("float32")


class SentenceEmbedder:
    name = "sentence"

    def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer  # optional dependency
        self.model_name = model
        self.model = SentenceTransformer(model)

    def fit(self, texts):
        return self

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self.model.encode(texts, normalize_embeddings=True), dtype="float32")

    def __getstate__(self):  # do not pickle the model weights; reload by name
        return {"model_name": self.model_name}

    def __setstate__(self, state):
        self.__init__(state["model_name"])


def _normalise(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=1, keepdims=True)
    return v / np.where(n == 0, 1, n)


class VectorStore:
    """Cosine-similarity index: FAISS if available, otherwise NumPy."""

    def __init__(self, vectors: np.ndarray):
        self.vectors = _normalise(vectors.astype("float32"))
        self.index = None
        try:
            import faiss  # optional dependency
            self.index = faiss.IndexFlatIP(self.vectors.shape[1])
            self.index.add(self.vectors)
        except ImportError:
            pass

    @property
    def backend(self) -> str:
        return "faiss" if self.index is not None else "numpy"

    def search(self, q: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        q = _normalise(q.astype("float32").reshape(1, -1))
        if self.index is not None:
            scores, ids = self.index.search(q, k)
            return scores[0], ids[0]
        sims = self.vectors @ q[0]
        ids = np.argsort(-sims)[:k]
        return sims[ids], ids

    def __getstate__(self):
        return {"vectors": self.vectors}

    def __setstate__(self, state):
        self.__init__(state["vectors"])


class KnowledgeBase:
    def __init__(self, chunks: list[Chunk], embedder, store: VectorStore):
        self.chunks, self.embedder, self.store = chunks, embedder, store

    @classmethod
    def build(cls, folder: str | Path = KNOWLEDGE_DIR, backend: str = "auto",
              extra_docs: list[tuple[str, str]] | None = None) -> "KnowledgeBase":
        chunks = chunk_documents(load_documents(folder) + (extra_docs or []))
        texts = [f"{c.title}. {c.text}" for c in chunks]
        embedder = None
        if backend in ("auto", "sentence"):
            try:
                embedder = SentenceEmbedder()
            except Exception:
                if backend == "sentence":
                    raise
        if embedder is None:
            embedder = TfidfEmbedder()
        embedder.fit(texts)
        return cls(chunks, embedder, VectorStore(embedder.encode(texts)))

    def search(self, query: str, k: int = 4, min_score: float = 0.05) -> list[dict]:
        scores, ids = self.store.search(self.embedder.encode([query])[0], k)
        return [{"id": int(i), "score": round(float(s), 3), "title": self.chunks[i].title,
                 "source": self.chunks[i].source, "text": self.chunks[i].text}
                for s, i in zip(scores, ids) if i >= 0 and s >= min_score]

    def info(self) -> dict:
        return {"chunks": len(self.chunks), "documents": len({c.source for c in self.chunks}),
                "embedder": self.embedder.name, "vector_store": self.store.backend}

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @staticmethod
    def load(path: str | Path) -> "KnowledgeBase":
        return joblib.load(path)
