"""Tool layer STEP 3 — bridge tra Agente 2 (ReAct / tool calling) e SQLite + RAG.

L'Agente 2 non legge il DB o le policy direttamente: chiama questi tool tramite
lo schema OpenAI ``OPENAI_TOOLS``. Noi eseguiamo la funzione Python corrispondente
in ``TOOL_MAP`` e restituiamo l'observation come stringa (JSON o testo formattato).

"""

from __future__ import annotations

import json
from typing import Any, Callable

from src.database import get_db_connection
from src.paths import POLICY_PATH
from src.rag import format_semantic_result, semantic_policy_search

# =====================================================================
# TOOL 1 — Stato ordine (SQLite tabella ``ordini``)
# =====================================================================


def get_order_status(order_id: str) -> str:
    """Recupera i dati di un ordine da SQLite e li serializza come JSON.

    Fonte di verità per l'Agente 2: evita che l'LLM inventi ``stato_spedizione``
    o ``importo``. Se l'ID non esiste, restituiamo un JSON di errore esplicito
    così il Resolver può rispondere al cliente senza allucinare i campi.

    Args:
        order_id: Chiave primaria ``id_ordine`` (es. ``ORD-101-LOST``).

    Returns:
        Stringa JSON: o i campi ordine, o ``{"errore": "...", "id_ordine": "..."}``.
    """
    # Normalizziamo spazi accidentali dal tool-call LLM (es. " ORD-101-LOST ").
    order_id_norm = (order_id or "").strip()
    if not order_id_norm:
        return json.dumps(
            {"errore": "order_id vuoto o mancante", "id_ordine": order_id},
            ensure_ascii=False,
        )

    # SELECT puntuale sulla PK: un solo record o nessuno (niente LIKE / fuzzy).
    sql_select = """
    SELECT id_ordine, email_cliente, importo, stato_spedizione
    FROM ordini
    WHERE id_ordine = ?;
    """

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql_select, (order_id_norm,))
        row = cursor.fetchone()

    if row is None:
        # Observation negativa strutturata: l'agente deve trattarla come "non trovato",
        # non come pretesto per inventare uno stato di spedizione.
        return json.dumps(
            {
                "errore": "ordine non trovato",
                "id_ordine": order_id_norm,
            },
            ensure_ascii=False,
        )

    id_ordine, email_cliente, importo, stato_spedizione = row
    """ MODO TRADIZIONALE (Senza Unpacking - Sconsigliato)
        id_ordine = row[0]
        email_cliente = row[1]
        importo = row[2]
        stato_spedizione = row[3]"""
    # SQLite restituisce DECIMAL come float/int a seconda dello storage;
    # forziamo float così il JSON è sempre numerico e confrontabile con la soglia 100€.
    payload = {
        "id_ordine": id_ordine,
        "email_cliente": email_cliente,
        "importo": float(importo),
        "stato_spedizione": stato_spedizione,
    }
    return json.dumps(payload, ensure_ascii=False)


# =====================================================================
# TOOL 2 — Policy di supporto (RAG semantica su policy_supporto.txt)
# =====================================================================


def get_support_policy(query: str) -> str:
    """Cerca il chunk di policy più rilevante rispetto alla query del Resolver.

    Delega a ``semantic_policy_search`` (embeddings + cosine su SQLite). Se nessun
    chunk supera la soglia di similarità, restituiamo un messaggio testuale chiaro:
    l'Agente 2 non deve inventare regole aziendali assenti dall'indice.

    Args:
        query: Domanda in linguaggio naturale (es. "ordine smarrito cosa offrire").

    Returns:
        Testo formattato con score RAG, oppure messaggio di "nessun match".
    """
    query_norm = (query or "").strip()
    if not query_norm:
        return "Errore: query vuota — impossibile cercare nelle policy di supporto."

    # POLICY_PATH punta a data/policy_supporto.txt (paths.py); l'indice è in SQLite.
    result = semantic_policy_search(query_norm, POLICY_PATH)
    if result is None:
        return (
            "Nessuna policy rilevante trovata per la query "
            f"(soglia di similarità non superata): {query_norm!r}"
        )

    # format_semantic_result aggiunge prefisso [RAG semantica | score=...] utile
    # in observation: l'operatore a terminale vede quanto era affidabile il match.
    return format_semantic_result(result)


# =====================================================================
# TOOL 3 — Rimborso monetario (didattico: nessun gateway pagamenti reale)
# =====================================================================


def issue_refund(order_id: str, reason: str) -> str:
    """Emette un rimborso monetario simulato per un ordine già verificato.

    STEP 5: l'esecuzione reale può essere intercettata dall'orchestratore se
    ``importo > 100€`` (HITL). Qui validiamo l'ID, rileggiamo l'importo da SQLite
    per coerenza con il breakpoint, e restituiamo un JSON di successo didattico.

    Args:
        order_id: Chiave primaria ordine (deve iniziare con ``ORD-``).
        reason: Motivazione breve del rimborso (audit / ticket).

    Returns:
        JSON di successo o errore strutturato (ordine assente, ID malformato).
    """
    order_id_norm = (order_id or "").strip()
    reason_norm = (reason or "").strip()

    if not order_id_norm:
        return json.dumps(
            {"errore": "order_id vuoto o mancante", "id_ordine": order_id},
            ensure_ascii=False,
        )

    # Convenzione Autobahn: tutti gli id ordine nel seed e nel triage usano ORD-.
    if not order_id_norm.upper().startswith("ORD-"):
        return json.dumps(
            {
                "errore": "order_id non valido: atteso prefisso ORD-",
                "id_ordine": order_id_norm,
            },
            ensure_ascii=False,
        )

    if not reason_norm:
        return json.dumps(
            {
                "errore": "reason vuota: serve una motivazione per il rimborso",
                "id_ordine": order_id_norm,
            },
            ensure_ascii=False,
        )

    sql_select = """
    SELECT id_ordine, importo
    FROM ordini
    WHERE id_ordine = ?;
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql_select, (order_id_norm,))
        row = cursor.fetchone()

    if row is None:
        return json.dumps(
            {
                "errore": "ordine non trovato — impossibile emettere rimborso",
                "id_ordine": order_id_norm,
            },
            ensure_ascii=False,
        )

    id_ordine_db, importo = row
    importo_float = float(importo)

    # Payload didattico: in produzione qui ci sarebbe l'ID transazione del PSP.
    payload = {
        "esito": "rimborso_emesso",
        "id_ordine": id_ordine_db,
        "importo_rimborsato_eur": importo_float,
        "motivazione": reason_norm,
        "messaggio": (
            f"Rimborso simulato di {importo_float:.2f}€ registrato per {id_ordine_db}."
        ),
    }
    return json.dumps(payload, ensure_ascii=False)


# =====================================================================
# Registry + schema OpenAI (function calling)
# =====================================================================

# Mappa nome tool (come dichiarato allo schema OpenAI) → callable Python.
# L'orchestratore/Resolver fa: TOOL_MAP[name](**args) dopo il parse del tool_call.
TOOL_MAP: dict[str, Callable[..., str]] = {
    "get_order_status": get_order_status,
    "get_support_policy": get_support_policy,
    "issue_refund": issue_refund,
}

# Schema tools nel formato Chat Completions API (type=function).
# ``parameters`` è JSON Schema: l'LLM deve riempire solo le proprietà dichiarate.
OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": (
                "Recupera da database lo stato di un ordine Autobahn: "
                "id_ordine, email_cliente, importo (euro) e stato_spedizione "
                "(es. Spedito, Smarrito, In Elaborazione). "
                "Usare sempre questo tool prima di promettere rimborsi o sostituzioni."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": (
                            "Identificativo ordine (chiave primaria), "
                            "es. ORD-101-LOST o ORD-999-OK."
                        ),
                    },
                },
                "required": ["order_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_support_policy",
            "description": (
                "Cerca nella knowledge base delle policy di supporto Autobahn "
                "(resi, spedizioni smarrite, soglie rimborso, articoli danneggiati, frodi). "
                "Passare una query in linguaggio naturale che descrive il caso del cliente."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Domanda o descrizione del caso da confrontare con le policy, "
                            "es. 'ordine smarrito cosa offrire al cliente'."
                        ),
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "issue_refund",
            "description": (
                "Emette un rimborso monetario diretto per un ordine già verificato "
                "(simulazione didattica Autobahn). Usare SOLO dopo get_order_status "
                "e get_support_policy quando la policy consente un rimborso in denaro. "
                "Per importi superiori a 100€ il sistema può sospendere il workflow "
                "in attesa di approvazione supervisore."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": (
                            "Identificativo ordine da rimborsare (es. ORD-302-REFUND-LOW)."
                        ),
                    },
                    "reason": {
                        "type": "string",
                        "description": (
                            "Motivazione sintetica del rimborso per audit "
                            "(es. 'reso entro 14 giorni', 'ordine smarrito — policy rimborso')."
                        ),
                    },
                },
                "required": ["order_id", "reason"],
                "additionalProperties": False,
            },
        },
    },
]


def execute_tool(name: str, arguments: dict[str, Any] | str) -> str:
    """Dispatch sicuro: nome tool OpenAI → funzione Python → observation stringa.

    Pensato per il loop ReAct dell'Agente 2: dopo ogni ``tool_calls`` dell'LLM
    si chiama questa funzione e si rimanda il risultato come messaggio ``tool``.

    Args:
        name: Nome della function nello schema (chiave di ``TOOL_MAP``).
        arguments: Dict già parsato, oppure stringa JSON grezza da ``tool_call.function.arguments``.

    Returns:
        Observation testuale/JSON da appendere alla cronologia chat.
    """
    print(f"[TOOL] {name}({arguments!r})")

    if name not in TOOL_MAP:
        # Non solleviamo: l'LLM può aver allucinato un nome tool inesistente.
        # Restituiamo errore in observation così può correggersi al turno successivo.
        return json.dumps(
            {"errore": f"tool sconosciuto o non disponibile: {name}"},
            ensure_ascii=False,
        )

    # L'API OpenAI consegna ``arguments`` come stringa JSON; accettiamo anche un dict
    # già deserializzato (comodo nei test unitari senza mockare l'intero tool_call).
    if isinstance(arguments, str):
        try:
            args_dict: dict[str, Any] = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as exc:
            return json.dumps(
                {
                    "errore": "arguments non è JSON valido",
                    "dettaglio": str(exc),
                    "raw": arguments,
                },
                ensure_ascii=False,
            )
    else:
        args_dict = dict(arguments)

    try:
        # **args_dict: i nomi proprietà nello schema devono coincidere coi parametri Python
        # (order_id / query). Se l'LLM manda chiavi extra, TypeError → catturato sotto.
        return TOOL_MAP[name](**args_dict)
    except TypeError as exc:
        # Tipicamente: parametro obbligatorio mancante o nome sbagliato nello schema call.
        return json.dumps(
            {
                "errore": f"argomenti non validi per {name}",
                "dettaglio": str(exc),
                "arguments": args_dict,
            },
            ensure_ascii=False,
        )
