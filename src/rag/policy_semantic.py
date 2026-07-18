"""
RAG semantica su data/policy.txt — Lezione 10 + 10B (ChromaDB).

Pipeline: paragraph chunking → embeddings OpenAI → query su ChromaDB (cosine).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from client import get_client
from rag.chroma_store import get_policy_collection, query_similar, reset_policy_store, upsert_policy_chunks

EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_THRESHOLD = 0.38


@dataclass(frozen=True)
class SemanticSearchResult:
    """Risultato della ricerca semantica su un chunk."""

    chunk_text: str
    score: float


def chunk_policy(text: str) -> list[str]:
    """Paragraph chunking: split su doppia interruzione di riga."""
    raw_chunks = text.split("\n\n")
    return [chunk.strip() for chunk in raw_chunks if chunk.strip()]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Similarità del coseno tra due vettori densi (utile in test)."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=True))
    #Attivando strict=True, Python lancia immediatamente un ValueError se le due liste non sono identiche in lunghezza
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def embed_texts(client: Any, texts: list[str]) -> list[list[float]]:
    """Genera embeddings batched tramite OpenAI."""
    if not texts:
        return []
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def clear_policy_index_cache() -> None:
    """Alias storico per i test: reset store Chroma."""
    reset_policy_store()


def semantic_policy_search(
    query: str,
    policy_path: Path,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    top_k: int = 1,
) -> SemanticSearchResult | None:
    """
    Cerca il chunk policy più simile alla query via ChromaDB.

    Restituisce None se nessun chunk supera la soglia.
    """
    if not policy_path.exists():
        return None

    client = get_client()
    collection = get_policy_collection(policy_path)

    if collection.count() == 0:
        chunks = chunk_policy(policy_path.read_text(encoding="utf-8"))
        if not chunks:
            return None
        chunk_embeddings = embed_texts(client, chunks)
        collection = upsert_policy_chunks(policy_path, chunks, chunk_embeddings)

    query_vec = embed_texts(client, [query])[0]
    scored = query_similar(collection, query_vec, top_k=top_k)
    if not scored:
        return None

    best_text, best_score = scored[0]
    if best_score < threshold:
        return None

    return SemanticSearchResult(chunk_text=best_text, score=best_score)


def format_semantic_result(result: SemanticSearchResult) -> str:
    """Formatta chunk + score per l'observation del tool."""
    return (
        f"[RAG semantica | score={result.score:.3f}]\n"
        f"{result.chunk_text}"
    )
