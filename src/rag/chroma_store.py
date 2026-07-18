"""
Store vettoriale ChromaDB per chunk policy — Lezione 10B.

Persistenza in data/chroma/; collection con metrica cosine.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import chromadb

from paths import CHROMA_PATH

COLLECTION_NAME = "policy_chunks"
COSINE_SPACE_METADATA = {"hnsw:space": "cosine"}

_chroma_client: chromadb.ClientAPI | None = None
_active_collection_name: str = COLLECTION_NAME


def policy_content_hash(policy_path: Path) -> str:
    return hashlib.sha256(policy_path.read_bytes()).hexdigest()


def set_chroma_client(client: chromadb.ClientAPI | None) -> None:
    """Inietta un client (es. EphemeralClient nei test) o ripristina il default."""
    global _chroma_client
    _chroma_client = client


def get_chroma_client() -> chromadb.ClientAPI:
    global _chroma_client
    if _chroma_client is None:
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return _chroma_client


def _get_or_create_collection(
    chroma: chromadb.ClientAPI,
    content_hash: str,
) -> chromadb.Collection:
    try:
        existing = chroma.get_collection(_active_collection_name)
        stored = (existing.metadata or {}).get("policy_hash")
        if stored == content_hash:
            return existing
        chroma.delete_collection(_active_collection_name)
    except Exception:
        pass

    return chroma.get_or_create_collection(
        name=_active_collection_name,
        metadata={**COSINE_SPACE_METADATA, "policy_hash": content_hash},
    )


def get_policy_collection(policy_path: Path) -> chromadb.Collection:
    """Restituisce la collection allineata al file policy (può essere vuota)."""
    resolved = policy_path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Policy non trovata: {resolved}")
    content_hash = policy_content_hash(resolved)
    return _get_or_create_collection(get_chroma_client(), content_hash)


def upsert_policy_chunks(
    policy_path: Path,
    chunks: list[str],
    embeddings: list[list[float]],
) -> chromadb.Collection:
    """Prima indicizzazione o re-indicizzazione dopo cambio hash."""
    if len(chunks) != len(embeddings):
        raise ValueError("chunks e embeddings devono avere la stessa lunghezza")
    collection = get_policy_collection(policy_path)
    if not chunks:
        return collection

    collection.upsert(
        ids=[f"chunk-{i}" for i in range(len(chunks))],
        documents=chunks,
        embeddings=embeddings,
        metadatas=[
            {"chunk_index": i, "source": str(policy_path.resolve())}
            for i in range(len(chunks))
        ],
    )
    return collection


def query_similar(
    collection: chromadb.Collection,
    query_embedding: list[float],
    *,
    top_k: int = 1,
) -> list[tuple[str, float]]:
    """
    Interroga ChromaDB. Restituisce (testo_chunk, score) con score = 1 - distance.
    """
    count = collection.count()
    if count == 0:
        return []

    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, count),
    )
    docs = result["documents"][0] if result.get("documents") else []
    distances = result["distances"][0] if result.get("distances") else []

    scored: list[tuple[str, float]] = []
    for doc, dist in zip(docs, distances, strict=True):
        if doc is None:
            continue
        scored.append((doc, 1.0 - float(dist)))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def reset_policy_store() -> None:
    """Svuota client e collection (test / reset didattico)."""
    global _chroma_client
    if _chroma_client is not None:
        try:
            _chroma_client.delete_collection(_active_collection_name)
        except Exception:
            pass
    _chroma_client = None
