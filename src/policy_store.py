"""
Store vettoriale policy su SQLite + numpy — Lezione 10B.

Persistenza embedding in customer_db.db; scoring in rag.py.

il db si compone di 2 tabelle: policy_chunks e policy_index_meta. Quest'ultima ha un solo record
con salvato l'hash256 del file di policy.
In policy_chunks sono salvati i relativi chunks di policy, l'embedding vettoriale (come blob)
e ad ogni record è associato l'hash256 che sta nella tabella policy_index_meta (quindi è lo stesso per ogni chunk!)

"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from src.database import get_db_connection


def policy_content_hash(policy_path: Path) -> str:
    return hashlib.sha256(policy_path.read_bytes()).hexdigest()


def embedding_to_blob(vec: list[float]) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def blob_to_embedding(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def get_stored_policy_hash() -> str | None:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT policy_hash FROM policy_index_meta WHERE id = 1"
        ).fetchone()
    return row[0] if row else None


def load_policy_chunks(policy_hash: str) -> list[tuple[str, np.ndarray]]:
#usa l'hash per recuperare i chunk dalla tabella. Se l'hash non è corretto non recupererà nessun chunk
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT chunk_text, embedding
            FROM policy_chunks
            WHERE policy_hash = ?
            ORDER BY chunk_index
            """,
            (policy_hash,),
        ).fetchall()
    return [(text, blob_to_embedding(blob)) for text, blob in rows]


def ensure_policy_indexed(
    policy_path: Path,
    chunks: list[str],
    embeddings: list[list[float]],
) -> str:
    """Indicizza i chunk se l'hash del file policy è cambiato o manca l'indice."""
    if len(chunks) != len(embeddings):
        raise ValueError("chunks e embeddings devono avere la stessa lunghezza")
        #le 2 liste devono avere la stessa lunghezza, ogni chunk deve avere il suo embedding!

    resolved = policy_path.resolve()
    content_hash = policy_content_hash(resolved)

    if get_stored_policy_hash() == content_hash and load_policy_chunks(content_hash):
        return content_hash

    with get_db_connection() as conn:#se l'hash ritornato è diverso da quello nel DB, cancello e rifaccio embedding
        conn.execute("DELETE FROM policy_chunks")
        conn.execute("DELETE FROM policy_index_meta")
        conn.execute(
            """
            INSERT INTO policy_index_meta (id, policy_hash, source_path)
            VALUES (1, ?, ?)
            """,
            (content_hash, str(resolved)),
        )
        conn.executemany(
            """
            INSERT INTO policy_chunks (chunk_index, chunk_text, embedding, policy_hash)
            VALUES (?, ?, ?, ?)
            """,
            [
                (i, chunk, embedding_to_blob(emb), content_hash)
                for i, (chunk, emb) in enumerate(zip(chunks, embeddings, strict=True))
            ],
        )

    return content_hash


def reset_policy_store() -> None:
    """Svuota indice policy (test / reset didattico)."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM policy_chunks")
        conn.execute("DELETE FROM policy_index_meta")
