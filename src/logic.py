"""Orchestrazione STEP 3 — Agente 1 Triage (e stub per il flusso lineare).

Agente 1: **una sola** chiamata OpenAI sync, output **solo JSON** hand-off.
Nessun tool, nessun accesso a DB/RAG: estrae mittente, lingua, riassunto e
(eventuale) id ordine sospetto dal testo email già passato dal guardrail.
"""

from __future__ import annotations

import json
import re
from typing import Any

from src.client import MODEL, get_client
from src.config import NONCE_END, NONCE_START
from src.errors import TriageError

# Lingue ammesse nel contratto hand-off A1 → A2 (piano STEP 3).
_LINGUE_AMMESSE = frozenset({"it", "en", "es", "de"})

# Campi obbligatori del JSON di triage (id_ordine_sospetto è opzionale).
_CAMPI_OBBLIGATORI = ("email_mittente", "lingua", "riassunto")

# Un solo retry se il modello restituisce JSON malformato o campi invalidi
# (piano: "JSON malformato → retry una volta o TriageError").
_MAX_TENTATIVI_TRIAGE = 2

# Lunghezza massima del testo *interno* a NONCE_* nel campo riassunto
# (i delimitatori non contano nel budget di 20 caratteri).
_RIASSUNTO_MAX_LEN = 20

def _build_system_prompt_triage() -> str:
    """Costruisce il system prompt A1 con i nonce reali da ``config``.

    I delimitatori NONCE_* arrivano dal ``.env``: vanno iniettati a runtime
    così il modello wrappa ``riassunto`` con gli stessi confini usati in input
    e dal parser che maschera quelle regioni in ``_estrai_oggetto_json``.
    """
    # f-string: le graffe dello schema JSON vanno raddoppiate ({{ / }}).
    return f"""\
Sei il Triage Analyst di Autobahn Customer Care.

Compito: analizzare il testo email del cliente (delimitato da confini di \
sicurezza) ed estrarre un JSON di hand-off per l'agente Resolver.

Regole:
- Rispondi SOLO con un oggetto JSON valido, senza markdown e senza testo extra.
- Non usare tool, database o knowledge base: lavora solo sul testo fornito.
- Non inventare un id ordine se non è esplicitamente presente nel testo \
  (in quel caso id_ordine_sospetto deve essere null).
- Non proporre soluzioni, rimborsi o priorità: quello spetta al Resolver.
- lingua deve essere uno tra: it, en, es, de (codice ISO a 2 lettere).
- Il campo "riassunto" DEVE essere wrappato tra i delimitatori di sicurezza \
  {NONCE_START} e {NONCE_END} (stessi confini usati sull'email in ingresso).
- Il testo del riassunto *dentro* i delimitatori deve avere al massimo \
  {_RIASSUNTO_MAX_LEN} caratteri (i nonce non contano nella lunghezza). \
  Esempio di valore: "{NONCE_START}\\nOrdine smarrito\\n{NONCE_END}"

Schema obbligatorio:
{{
  "email_mittente": "stringa email o stringa vuota se assente",
  "lingua": "it|en|es|de",
  "riassunto": "{NONCE_START}\\nmax {_RIASSUNTO_MAX_LEN} caratteri\\n{NONCE_END}",
  "id_ordine_sospetto": "es. ORD-101-LOST oppure null"
}}
"""


def wrap_user_text_with_nonce(testo: str) -> str:
    """Avvolge il testo utente tra NONCE_START e NONCE_END.

    I confini nonce (da ``config`` / ``.env``) mitigano prompt injection:
    il modello deve trattare solo il contenuto *dentro* i delimitatori come
    dati non affidabili, non come istruzioni di sistema.
    """
    # Strip leggero: evita newline spurie ai bordi senza alterare il corpo email.
    corpo = (testo or "").strip()
    return f"{NONCE_START}\n{corpo}\n{NONCE_END}"


def _maschera_regioni_nonce(testo: str) -> str:
    """Sostituisce ogni blocco NONCE_START…NONCE_END con spazi della stessa lunghezza.

    Serve al fallback regex ``\\{{...\\}}``: eventuali graffe o testo spurio
    *dentro* il riassunto (dati non affidabili) non devono spostare inizio/fine
    del match sull'oggetto JSON esterno. Stessa lunghezza ⇒ gli indici restano
    allineati al testo originale, da cui poi ritagliamo la sottostringa reale.

    Visto che il json verrà estratto da una stringa (e ad inizio-fine json, potrebbero esserci ulteriori
    caratteri di markdown) è importante sostituire il testo tra i nonce con degli spazi in numero equivalente
    per mantenere la lunghezza totale della stringa
    """
    # re.escape: i nonce tipici contengono [, ], _ — altrimenti la regex li
    # interpreterebbe come classi di caratteri / quantificatori.
    pattern = re.compile(
        re.escape(NONCE_START) + r".*?" + re.escape(NONCE_END),
        flags=re.DOTALL,
    )
    # lambda m: " " * len(...): placeholder neutro, nessuna '{' o '}' residua.
    return pattern.sub(lambda m: " " * len(m.group(0)), testo)


def _trova_span_oggetto_json(testo: str) -> tuple[int, int] | None:
    """Trova start/end (esclusivo) del primo oggetto ``{...}`` bilanciato.

    Lavora su una copia con regioni nonce mascherate: graffe dentro
    NONCE_START…NONCE_END non alterano il conteggio. Gli indici restano
    validi sul testo originale (placeholder a lunghezza invariata).
    """
    mascherato = _maschera_regioni_nonce(testo)
    start = mascherato.find("{")#il .find conta i caratteri prima di trovare {, se non trova graffe { restituisce -1 
    if start < 0: #quindi start < 0 vuol dire -1 quindi ritorna None
        return None

    # Contatore di profondità: +1 su '{', -1 su '}'. A zero siamo fuori
    # dall'oggetto radice — ignorando stringhe JSON sarebbe più corretto,
    # ma sul testo mascherato le graffe "pericolose" del riassunto sono già spazi.
    profondita = 0
    for i in range(start, len(mascherato)):
        ch = mascherato[i]
        if ch == "{":
            profondita += 1
        elif ch == "}":
            profondita -= 1
            if profondita == 0:
                return (start, i + 1)#ritorna la posizione dei caratteri da dove inizia il json "{" e dove finisce "}"
            if profondita < 0:
                # '}' spuria prima di chiudere: abort
                return None
    return None


def _estrai_oggetto_json(raw: str) -> dict[str, Any]:
    """Parsa la risposta LLM in un dict, tollerando fence markdown accidentali.

    Con ``response_format=json_object`` di solito arriva JSON puro; alcuni
    modelli comunque wrappano in `` ```json ... ``` ``. Estraiamo il primo
    oggetto ``{...}`` bilanciato, **ignorando** tutto ciò che sta tra
    NONCE_START e NONCE_END (es. graffe nel ``riassunto`` wrappato).
    """
    testo = (raw or "").strip()
    if not testo:
        raise TriageError("Risposta triage vuota: impossibile parsare JSON.")

    try:
        parsed = json.loads(testo)
    except json.JSONDecodeError:
        # Fallback: span bilanciato su testo con nonce mascherati, slice su originale.
        span = _trova_span_oggetto_json(testo)#controlla se il parsing json è fallito per via di 
        #caratteri prima o dopo le {}
        if span is None:#se non ha trovato {} coerenti di json all'interno della stringa
            raise TriageError(
                f"Risposta triage non contiene JSON oggetto: {testo[:200]!r}"
            ) from None
        candidato = testo[span[0] : span[1]]#porzione di testo tra span di inizio e fine delle {} più esterne
        try:
            parsed = json.loads(candidato)
        except json.JSONDecodeError as exc:
            raise TriageError(
                f"JSON triage malformato: {exc}. Raw={testo[:200]!r}"
            ) from exc

    if not isinstance(parsed, dict):
        raise TriageError(
            f"JSON triage non è un oggetto (dict): tipo={type(parsed).__name__}"
        )
    return parsed


def _normalizza_e_valida_triage(payload: dict[str, Any]) -> dict[str, Any]:
    """Valida e normalizza il contratto hand-off A1 → A2.

    Restituisce un dict con chiavi stabili, così A2 non deve gestire alias
    o tipi misti (es. id ordine numerico vs stringa).
    """
    mancanti = [c for c in _CAMPI_OBBLIGATORI if c not in payload]#controlla se A1 ha mancato 
    #campi obbligatori nel json
    if mancanti:
        raise TriageError(
            f"JSON triage incompleto, campi mancanti: {mancanti}. "
            f"Chiavi ricevute: {sorted(payload.keys())}"
        )

    email = payload.get("email_mittente")
    lingua = payload.get("lingua")
    riassunto = payload.get("riassunto")
    id_ordine = payload.get("id_ordine_sospetto", None)

    # Coercizione a stringa: l'LLM a volte manda null su email/riassunto.
    if email is None:
        email = ""
    if not isinstance(email, str):
        email = str(email)

    if not isinstance(lingua, str):
        raise TriageError(f"Campo lingua non valido: {lingua!r}")
    lingua_norm = lingua.strip().lower()
    if lingua_norm not in _LINGUE_AMMESSE:
        raise TriageError(
            f"lingua={lingua!r} non ammessa; attese: {sorted(_LINGUE_AMMESSE)}"
        )

    if riassunto is None or (isinstance(riassunto, str) and not riassunto.strip()):
        raise TriageError("Campo riassunto vuoto o mancante.")
    if not isinstance(riassunto, str):
        riassunto = str(riassunto)

    # Budget di lunghezza sul solo corpo tra nonce (o sull'intero valore se
    # il modello ha omesso i delimitatori): i marker NONCE_* non contano.
    corpo_riassunto = riassunto.strip()
    if corpo_riassunto.startswith(NONCE_START) and NONCE_END in corpo_riassunto:
        # Ritagliamo tra fine START e inizio END, poi strip newline tipiche del wrap.
        dopo_start = corpo_riassunto[len(NONCE_START) :]
        idx_end = dopo_start.rfind(NONCE_END)
        corpo_riassunto = dopo_start[:idx_end].strip()#ritaglio senza nonce del testo riassunto 
    if len(corpo_riassunto) > _RIASSUNTO_MAX_LEN:
        raise TriageError(
            f"riassunto troppo lungo: {len(corpo_riassunto)} caratteri "
            f"(max {_RIASSUNTO_MAX_LEN}): {corpo_riassunto!r}"
        )
    if not corpo_riassunto:
        raise TriageError("Campo riassunto vuoto tra i delimitatori nonce.")

    # id_ordine_sospetto: null / "" / "null" → None (non inventiamo ID).
    if id_ordine is None:
        id_norm: str | None = None
    elif isinstance(id_ordine, str):
        stripped = id_ordine.strip()
        # Alcuni modelli serializzano null come stringa letterale "null".
        id_norm = None if stripped == "" or stripped.lower() == "null" else stripped
    else:
        # Se arriva un numero, lo serializziamo: meglio stringa stabile che TypeError a valle.
        id_norm = str(id_ordine)

    return {
        "email_mittente": email.strip(),
        "lingua": lingua_norm,
        "riassunto": riassunto.strip(),
        "id_ordine_sospetto": id_norm,
    }


def _chiama_llm_triage(testo_con_nonce: str) -> str:
    """Esegue la singola chiamata Chat Completions per il Triage Analyst.

    ``response_format`` forza un oggetto JSON (non array/testo libero),
    riducendo i fallimenti di parse senza introdurre tool calling.
    """
    client = get_client()
    response = client.chat.completions.create(
        model=MODEL,
        # temperature bassa: triage è estrazione strutturata, non creatività.
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            # Prompt ricostruito a ogni call: include i NONCE_* correnti da config.
            {"role": "system", "content": _build_system_prompt_triage()},
            {
                "role": "user",
                # Il testo utente resta dentro i nonce: il system prompt spiega
                # che ciò che sta tra i confini sono DATI, non istruzioni.
                "content": (
                    "Analizza la seguente email cliente e restituisci il JSON "
                    "di hand-off.\n\n"
                    f"{testo_con_nonce}"
                ),
            },
        ],
    )

    # Difesa: content può essere None se il provider taglia o rifiuta l'output.
    content = response.choices[0].message.content
    if content is None:
        raise TriageError("Risposta OpenAI senza content (message.content is None).")
    return content


def run_triage_agent(testo: str) -> dict[str, Any]:
    """Agente 1 — Triage: 1 chiamata LLM (con eventuale retry) → JSON hand-off.

    Args:
        testo: Corpo email già sanificato dal guardrail (nessun DB/RAG qui).

    Returns:
        Dict con ``email_mittente``, ``lingua``, ``riassunto``,
        ``id_ordine_sospetto`` (str | None).

    Raises:
        TriageError: dopo esaurimento dei tentativi di parse/validazione,
            o se la chiamata API fallisce in modo non recuperabile lato parse.
    """
    print("[TRIAGE] Avvio Agente 1 (estrazione JSON, zero tools).")

    # Nonce applicato una sola volta fuori dal loop: il retry ripete solo la
    # chiamata LLM sullo stesso payload delimitato, non altera i confini.
    testo_protetto = wrap_user_text_with_nonce(testo)

    ultimo_errore: Exception | None = None
    for tentativo in range(1, _MAX_TENTATIVI_TRIAGE + 1):
        try:
            print(f"[TRIAGE] Chiamata LLM tentativo {tentativo}/{_MAX_TENTATIVI_TRIAGE}...")
            raw = _chiama_llm_triage(testo_protetto)
            print(f"[TRIAGE] Raw LLM: {raw[:300]!r}")

            # Parse → validazione contratto: entrambi possono fallire e triggerare retry.
            #perchè l'eccezione fa ripartire il for
            payload = _estrai_oggetto_json(raw)
            handoff = _normalizza_e_valida_triage(payload)

            print(
                "[TRIAGE] Hand-off pronto | "
                f"lingua={handoff['lingua']} | "
                f"email={handoff['email_mittente']!r} | "
                f"id_ordine={handoff['id_ordine_sospetto']!r}"
            )
            return handoff

        except TriageError as exc:
            ultimo_errore = exc
            print(f"[TRIAGE] Tentativo {tentativo} fallito: {exc}")
            # Altri errori (rete, auth OpenAI) non sono "JSON malformato":
            # li lasciamo propagare senza consumare il retry di parse.

    # Esauriti i tentativi: superficie unica verso l'orchestratore.
    raise TriageError(
        f"Triage fallito dopo {_MAX_TENTATIVI_TRIAGE} tentativi: {ultimo_errore}"
    ) from ultimo_errore
