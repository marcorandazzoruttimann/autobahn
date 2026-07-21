"""
RAG semantica su data/policy_supporto.txt — Lezione 10 + 10B.

Pipeline: paragraph chunking → embeddings OpenAI → persistenza SQLite → cosine_similarity.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from src.client import get_client
from src.rag.policy_store import (
    ensure_policy_indexed,
    get_stored_policy_hash,
    load_policy_chunks,
    reset_policy_store,
)

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


def cosine_similarity(
    vec_a: list[float] | np.ndarray,
    vec_b: list[float] | np.ndarray,
) -> float:
    """Similarità del coseno tra due vettori densi."""
    a = np.asarray(vec_a, dtype=np.float64)
    b = np.asarray(vec_b, dtype=np.float64)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def embed_texts(client: Any, texts: list[str]) -> list[list[float]]:
    """Genera embeddings batched tramite OpenAI."""
    if not texts:
        return []
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]#invia la lista chunk a openai e restituisce gli embeddings


def query_similar(
    query_embedding: list[float],
    policy_hash: str,
    *,
    top_k: int = 1,
) -> list[tuple[str, float]]:
    """Carica tutti i chunk da SQLite e restituisce i top_k per cosine_similarity."""
    chunks = load_policy_chunks(policy_hash)
    if not chunks:
        return []

    scored = [
        (text, cosine_similarity(query_embedding, emb))
        for text, emb in chunks
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:top_k]


def clear_policy_index_cache() -> None:
    """Alias storico per i test: reset store SQLite."""
    reset_policy_store()


def semantic_policy_search(
    query: str,
    policy_path: Path,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    top_k: int = 1,
) -> SemanticSearchResult | None:
    """
    Cerca il chunk policy più simile alla query via SQLite + cosine_similarity.

    Restituisce None se nessun chunk supera la soglia.
    """
    if not policy_path.exists():
        return None

    client = get_client()
    policy_hash = get_stored_policy_hash()#recupera l'ash dalla tabella

    if policy_hash is None or not load_policy_chunks(policy_hash):
        chunks = chunk_policy(policy_path.read_text(encoding="utf-8"))#ritorna una lista di chunks dal testo policy
        if not chunks:
            return None
        chunk_embeddings = embed_texts(client, chunks)#chiama openai e si fa restituire la lista di embeddings
        policy_hash = ensure_policy_indexed(policy_path, chunks, chunk_embeddings)#ritorna l'hash
        #assicura che gli hash contenuti nelle 2 tabelle siano identici, altrimenti ricrea le tabelle

    query_vec = embed_texts(client, [query])[0]#fa l'embedding della sola query di confronto
    scored = query_similar(query_vec, policy_hash, top_k=top_k)#ritorna la lista di tuple con con punteggio più alto
    if not scored:
        return None

    best_text, best_score = scored[0]
    if best_score < threshold:
        return None

    return SemanticSearchResult(chunk_text=best_text, score=best_score)#non è funzione, ma dataclass!


def warm_policy_index_from_file(policy_path: Path) -> None:
    """Indicizza o riallinea l'indice policy se mancante o stale."""
    if not policy_path.exists():
        return

    from src.rag.policy_store import (
        ensure_policy_indexed,
        get_stored_policy_hash,
        load_policy_chunks,
        policy_content_hash,
    )

    current_hash = policy_content_hash(policy_path)
    if get_stored_policy_hash() == current_hash and load_policy_chunks(current_hash):
        return #se il policy hash in tabella e i chunk in tabella hanno questo hash allora ok

    client = get_client()#se ci sono problemi di hash, ripopola la tabella
    chunks = chunk_policy(policy_path.read_text(encoding="utf-8"))
    if not chunks:
        return
    embeddings = embed_texts(client, chunks)
    ensure_policy_indexed(policy_path, chunks, embeddings)


def format_semantic_result(result: SemanticSearchResult) -> str:
    """Formatta chunk + score per l'observation del tool."""
    return (
        f"[RAG semantica | score={result.score:.3f}]\n"
        f"{result.chunk_text}"
    )
