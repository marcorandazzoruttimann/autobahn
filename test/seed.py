"""Seed SQLite per demo e test end-to-end Autobahn.

Popola ``ordini`` e ``workflow_states`` con record allineati agli scenari
in ``src/main.py`` (ordini OK/smarriti, rimborso basso/alto, resume HITL).

Invocato da ``init_db`` in ``src/database.py`` a ogni bootstrap; eseguibile
anche standalone con ``python -m test.seed``.
"""

from __future__ import annotations

import json
import sqlite3

# ---------------------------------------------------------------------
# Costanti esportate: stessi ID usati da demo, smoke e documentazione.
# ---------------------------------------------------------------------

# Sessione pre-congelata per ``python -m src.main --resume SESS-TEST-RESUME-01``.
ID_SESSIONE_RESUME_DEMO = "SESS-TEST-RESUME-01"

# Tuple (id_ordine, email_cliente, importo, stato_spedizione) — fonte unica seed.
ORDINI_DEMO: tuple[tuple[str, str, float, str], ...] = (
    ("ORD-999-OK", "mario.rossi@example.com", 45.50, "Spedito"),
    ("ORD-101-LOST", "luca.bianchi@example.com", 89.90, "Smarrito"),
    ("ORD-302-REFUND-LOW", "giulia.verdi@example.com", 35.00, "In Elaborazione"),
    ("ORD-404-REFUND-HIGH", "antonio.neri@example.com", 250.00, "In Elaborazione"),
)

SQL_INSERT_ORDINE = """
INSERT OR IGNORE INTO ordini (id_ordine, email_cliente, importo, stato_spedizione)
VALUES (?, ?, ?, ?);
"""

SQL_UPSERT_WORKFLOW = """
INSERT OR REPLACE INTO workflow_states (
    id_sessione, email_cliente, id_ordine, stato_workflow, messaggi_serializzati
)
VALUES (?, ?, ?, ?, ?);
"""


def _messaggi_workflow_resume_demo() -> list[dict]:
    """Cronologia Resolver al breakpoint HITL (assistant + tool_calls, no observation).

    ``resume_hitl_workflow`` si aspetta esattamente questo stato: l'ultimo
    messaggio è ``assistant`` con ``issue_refund`` pendente su ORD-404-REFUND-HIGH.
    """
    return [
        {
            "role": "system",
            "content": (
                "Sei il Customer Resolver di Autobahn Customer Care. "
                "Usa i tool e chiudi con JSON finale."
            ),
        },
        {
            "role": "user",
            "content": (
                "Hand-off JSON dal Triage Analyst:\n"
                '{"email_cliente": "antonio.neri@example.com", '
                '"lingua": "it", "riassunto": "rimborso alto", '
                '"id_ordine_sospetto": "ORD-404-REFUND-HIGH"}\n\n'
                "Voglio il rimborso per l'ordine ORD-404-REFUND-HIGH, è rotto."
            ),
        },
        {
            "role": "assistant",
            # content None: al freeze tipico l'LLM emette solo tool_calls.
            "content": None,
            "tool_calls": [
                {
                    "id": "call_seed_refund_404",
                    "type": "function",
                    "function": {
                        "name": "issue_refund",
                        # arguments come stringa JSON grezza (contratto Chat Completions).
                        "arguments": json.dumps(
                            {
                                "order_id": "ORD-404-REFUND-HIGH",
                                "reason": (
                                    "prodotto difettoso — richiesta rimborso "
                                    "oltre soglia HITL"
                                ),
                            },
                            ensure_ascii=False,
                        ),
                    },
                }
            ],
        },
    ]


def seed_db(conn: sqlite3.Connection) -> None:
    """Popola il database con dati di test per tutti gli scenari previsti dal progetto.

    Args:
        conn: Connessione SQLite aperta (stessa transazione di ``init_db``).
    """
    cursor = conn.cursor()

    # --- Ordini demo ---
    # executemany: stessa INSERT ripetuta su N tuple (batch efficiente).
    cursor.executemany(SQL_INSERT_ORDINE, ORDINI_DEMO)

    # --- Workflow HITL pre-congelato (resume demo) ---
    # json.dumps su messaggi_serializzati: stesso formato di save_workflow_pending.
    messaggi_finti_json = json.dumps(
        _messaggi_workflow_resume_demo(),
        ensure_ascii=False,
    )

    # INSERT OR REPLACE: riallinea il seed al contratto resume se la riga esiste
    # già con messaggi obsoleti (IGNORE lascerebbe SESS-TEST-RESUME-01 stale).
    cursor.execute(
        SQL_UPSERT_WORKFLOW,
        (
            ID_SESSIONE_RESUME_DEMO,
            "antonio.neri@example.com",
            "ORD-404-REFUND-HIGH",
            "PENDING_APPROVAL",
            messaggi_finti_json,
        ),
    )

    print("    [+] Dati di test (seed) inseriti con successo (o già esistenti).")


def run_seed() -> None:
    """Applica il seed su DB già inizializzato (entry-point CLI ``python -m test.seed``)."""
    # Import lazy: evita import circolare database ↔ test.seed al load del modulo.
    from src.database import get_db_connection

    with get_db_connection() as conn:
        seed_db(conn)


if __name__ == "__main__":
    run_seed()
