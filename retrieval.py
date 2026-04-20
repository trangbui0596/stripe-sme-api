"""
TF-IDF search over ingested Stripe legal document chunks.
Loaded once at startup; shared across all requests.
"""

import pickle
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

STORE_PATH = "store.pkl"

_chunks: list[str] = []
_sources: list[str] = []
_vectorizer = None
_matrix = None


def load_store(path: str = STORE_PATH):
    global _chunks, _sources, _vectorizer, _matrix
    with open(path, "rb") as f:
        store = pickle.load(f)
    _chunks = store["chunks"]
    _sources = store.get("sources", ["Unknown"] * len(_chunks))
    _vectorizer = store["vectorizer"]
    _matrix = store["matrix"]
    print(f"Loaded {len(_chunks)} chunks from {path}")


def search(query: str, top_k: int = 5) -> list[dict]:
    query_vec = _vectorizer.transform([query])
    scores = cosine_similarity(query_vec, _matrix).flatten()
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [{"text": _chunks[i], "source": _sources[i]} for i in top_indices]
