import json
import sqlite3
from typing import Any, Generator
from contextlib import contextmanager

# AGGIORNAMENTO: Importiamo i percorsi centralizzati e la funzione di utility
from src.paths import DB_PATH, ensure_directories_exist

# =====================================================================
# DEFINIZIONE DELLE QUERY DI CREAZIONE TABELLE
# =====================================================================

SQL_CREATE_ORDINI_TABLE = """
CREATE TABLE IF NOT EXISTS ordini (
    id_ordine VARCHAR(50) PRIMARY KEY,
    email_cliente VARCHAR(255) NOT NULL,
    importo DECIMAL(10, 2) NOT NULL,
    stato_spedizione VARCHAR(50) NOT NULL
);
"""

SQL_CREATE_ORDINI_INDEX = """
CREATE INDEX IF NOT EXISTS idx_ordini_email ON ordini(email_cliente);
"""

SQL_CREATE_WORKFLOW_STATES_TABLE = """
CREATE TABLE IF NOT EXISTS workflow_states (
    id_sessione VARCHAR(100) PRIMARY KEY,
    email_cliente VARCHAR(255) NOT NULL,
    id_ordine VARCHAR(50),
    stato_workflow VARCHAR(50) DEFAULT 'PENDING_APPROVAL',
    messaggi_serializzati TEXT NOT NULL,
    data_congelamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_ordine) REFERENCES ordini(id_ordine)
);
"""

SQL_CREATE_SECURITY_AUDIT_TABLE = """
CREATE TABLE IF NOT EXISTS security_audit (
    id_audit INTEGER PRIMARY KEY AUTOINCREMENT,
    email_cliente VARCHAR(255),
    input_testo TEXT NOT NULL,
    categoria_attacco VARCHAR(100) DEFAULT 'PROMPT_INJECTION',
    stato_ticket VARCHAR(50) DEFAULT 'ATTACK_BLOCKED',
    data_rilevamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SQL_CREATE_FINAL_RESPONSE_TABLE = """
CREATE TABLE IF NOT EXISTS final_response (
    id_risposta INTEGER PRIMARY KEY AUTOINCREMENT,
    id_ordine VARCHAR(50),
    email_cliente VARCHAR(255) NOT NULL,
    risposta_generata TEXT NOT NULL,
    priorita_ticket VARCHAR(20) NOT NULL,
    token_input INTEGER NOT NULL,
    token_output INTEGER NOT NULL,
    costo_calcolato REAL NOT NULL,
    latenza_secondi REAL NOT NULL,
    data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_ordine) REFERENCES ordini(id_ordine)
);
"""

SQL_CREATE_POLICY_INDEX_META_TABLE = """
CREATE TABLE IF NOT EXISTS policy_index_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    policy_hash TEXT NOT NULL,
    source_path TEXT NOT NULL,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SQL_CREATE_POLICY_CHUNKS_TABLE = """
CREATE TABLE IF NOT EXISTS policy_chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding BLOB NOT NULL,
    policy_hash TEXT NOT NULL
);
"""

SQL_CREATE_POLICY_CHUNKS_HASH_INDEX = """
CREATE INDEX IF NOT EXISTS idx_policy_chunks_hash ON policy_chunks(policy_hash);
"""

# =====================================================================
# FUNZIONI DI SEEDING (DATI DI TEST INIZIALI)
# =====================================================================

def seed_db(conn: sqlite3.Connection) -> None:
    """
    Popola il database con dati di test realistici per coprire tutti gli
    scenari previsti dal PDF (standard, smarriti, rimborsi alti/bassi).
    """
    cursor = conn.cursor()

    # Scenario 1: Lista di ordini di test
    # Peculiarità Python: Usiamo una lista di tuple. Il metodo cursor.executemany() 
    # è estremamente efficiente in Python per eseguire la stessa query SQL 
    # su un intero iterabile di parametri in un solo colpo (batching).
    ordini_test = [
        # (id_ordine, email_cliente, importo, stato_spedizione)
        ("ORD-999-OK", "mario.rossi@example.com", 45.50, "Spedito"),
        ("ORD-101-LOST", "luca.bianchi@example.com", 89.90, "Smarrito"),
        ("ORD-302-REFUND-LOW", "giulia.verdi@example.com", 35.00, "In Elaborazione"),
        ("ORD-404-REFUND-HIGH", "antonio.neri@example.com", 250.00, "In Elaborazione")
    ]

    # Peculiarità Python/SQL: Usiamo 'INSERT OR IGNORE' per evitare che l'esecuzione 
    # del bootstrap fallisca con un 'IntegrityError' (chiave primaria duplicata) 
    # se avviamo il main più di una volta.
    sql_insert_ordine = """
    INSERT OR IGNORE INTO ordini (id_ordine, email_cliente, importo, stato_spedizione)
    VALUES (?, ?, ?, ?);
    """
    cursor.executemany(sql_insert_ordine, ordini_test)

    # Scenario 2: Record di pre-congelamento in workflow_states (Per testare il Resume dello STEP 5)
    # Creiamo una sessione finta congelata per l'utente 'antonio.neri@example.com' 
    # che richiede un rimborso sull'ordine da 250€
    id_sessione_test = "SESS-TEST-RESUME-01"
    
    # Peculiarità Python: Simuliamo la serializzazione JSON di una cronologia di messaggi dell'Agente 2.
    # In Python, le triple virgolette ci permettono di formattare stringhe multilinea complesse.
    messaggi_finti_json = """[
        {"role": "system", "content": "Sei l'Agente 2 Customer Resolver."},
        {"role": "user", "content": "Voglio il rimborso per l'ordine ORD-404-REFUND-HIGH, è rotto."},
        {"role": "assistant", "content": "Ho verificato l'ordine ORD-404-REFUND-HIGH di importo 250.00€. Procedo ad attivare il tool di rimborso."}
    ]"""

    sql_insert_workflow = """
    INSERT OR IGNORE INTO workflow_states (id_sessione, email_cliente, id_ordine, stato_workflow, messaggi_serializzati)
    VALUES (?, ?, ?, ?, ?);
    """
    cursor.execute(sql_insert_workflow, (
        id_sessione_test, 
        "antonio.neri@example.com", 
        "ORD-404-REFUND-HIGH", 
        "PENDING_APPROVAL", 
        messaggi_finti_json
    ))

    print("    [+] Dati di test (seed) inseriti con successo (o già esistenti).")

    
# =====================================================================
# GESTIONE CONNESSIONE (Context Manager)
# =====================================================================

@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager per gestire in sicurezza l'apertura e la chiusura 
    della connessione al database SQLite.
    """
    # AGGIORNAMENTO: Usiamo la utility centralizzata di paths.py
    # per essere sicuri che la cartella 'data/' esista prima di aprire il file .db
    ensure_directories_exist()
    
    # Peculiarità Python: sqlite3.connect accetta sia stringhe che oggetti Path.
    # Internamente, SQLite si aspetta una stringa, ma Python converte automaticamente 
    # l'oggetto Path in stringa grazie al protocollo dunder '__fspath__'.
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# =====================================================================
# PERSISTENZA AUDIT SICUREZZA
# =====================================================================

def insert_security_audit(
    *,
    input_testo: str,
    email_cliente: str | None = None,
    categoria_attacco: str = "PROMPT_INJECTION",
    stato_ticket: str = "ATTACK_BLOCKED",
) -> int:
    """Registra su ``security_audit`` un input bloccato dal guardrail.

    La traccia persistente dell'attacco è solo SQLite (nessun logger su file):
    ``guardrails.py`` chiama questa funzione prima di sollevare
    ``SecurityGuardrailError``, così l'operatore può correlare l'allerta
    a terminale con ``id_audit``.

    Args:
        input_testo: Testo email completo (o estratto) che ha attivato il blocco.
        email_cliente: Mittente se già noto; ``None`` se il guardrail gira prima
            dell'estrazione dell'indirizzo (es. scan su body grezzo).
        categoria_attacco: Etichetta derivata dai vettori (es. ``TOOL_HIJACK``,
            ``POLICY_OVERRIDE``); default allineato allo schema tabella.
        stato_ticket: Stato fissato a ``ATTACK_BLOCKED`` per input malevoli.

    Returns:
        ``id_audit`` generato da AUTOINCREMENT (chiave per join e print operativo).
    """
    # Parametri posizionali (?): sqlite3 non espone binding nominati; l'ordine
    # segue le colonne della INSERT, escludendo id_audit e data_rilevamento (DEFAULT).
    sql_insert_audit = """
    INSERT INTO security_audit (email_cliente, input_testo, categoria_attacco, stato_ticket)
    VALUES (?, ?, ?, ?);
    """

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            sql_insert_audit,
            (email_cliente, input_testo, categoria_attacco, stato_ticket),
        )
        # lastrowid è valorizzato solo dopo execute su una INSERT con INTEGER PRIMARY KEY
        # AUTOINCREMENT; lo restituiamo al chiamante per includerlo nel ticket dict.
        return int(cursor.lastrowid)
        #La proprietà cursor.lastrowid recupera immediatamente dopo l'esecuzione della query (execute) 
        #quell'ID autogenerato dalla sessione corrente della connessione, 
        #senza che tu debba fare una successiva SELECT MAX(id) o SELECT id WHERE ....


# =====================================================================
# PERSISTENZA RISPOSTA FINALE + TELEMETRIA
# =====================================================================

# Fallback NOT NULL per email_cliente quando A1 non estrae un mittente:
# lo schema richiede VARCHAR NOT NULL, ma l'LLM può restituire "".
_EMAIL_CLIENTE_FALLBACK = "sconosciuto@local"


def insert_final_response(
    *,
    email_cliente: str,
    risposta_generata: str,
    priorita_ticket: str,
    token_input: int,
    token_output: int,
    costo_calcolato: float,
    latenza_secondi: float,
    id_ordine: str | None = None,
) -> int:
    """Persiste su ``final_response`` la risposta A2 e la telemetria STEP 4.

    Chiamata solo dal path felice di ``elabora_email`` (mai su
    ``ATTACK_BLOCKED``): così i ticket bloccati dal guardrail non sporcano
    la tabella delle risposte operative.

    Vincolo FK su ``id_ordine`` → ``ordini(id_ordine)``: se l'ID non esiste
    (allucinazione LLM, ordine assente, o ``None``), inseriamo ``NULL``
    invece di far fallire l'INSERT con IntegrityError. La risposta resta
    comunque tracciata con token/costo/latenza.

    Args:
        email_cliente: Mittente da hand-off A1; se vuoto/None viene sostituito
            con ``sconosciuto@local`` per rispettare ``NOT NULL``.
        risposta_generata: Testo ``soluzione_proposta`` del JSON Resolver.
        priorita_ticket: ``priorita`` A2 già normalizzata (Low|Medium|Critical).
        token_input / token_output: Accumulo ``response.usage`` A1+A2.
        costo_calcolato: Risultato equazione PDF (in × 5e-6 + out × 1.5e-5).
        latenza_secondi: Delta wall-clock post-guardrail → pre-INSERT.
        id_ordine: ID dal JSON A2; ``None`` o ID sconosciuto → colonna NULL.

    Returns:
        ``id_risposta`` AUTOINCREMENT (utile a print ``[TELEMETRIA]`` e al
        dict restituito dalla pipeline per la demo in ``main``).
    """
    # Normalizziamo l'email PRIMA della INSERT: stringa vuota / solo spazi
    # violerebbe NOT NULL in modo silenzioso se passassimo "" (SQLite accetta
    # "" come valore non-NULL). Il fallback didattico è fissato dal piano.
    email_norm = (email_cliente or "").strip() or _EMAIL_CLIENTE_FALLBACK

    sql_insert_final = """
    INSERT INTO final_response (
        id_ordine,
        email_cliente,
        risposta_generata,
        priorita_ticket,
        token_input,
        token_output,
        costo_calcolato,
        latenza_secondi
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """

    # Verifica esistenza ordine: SELECT 1 è più economico di un INSERT che
    # fallisce e richiede rollback; con PRAGMA foreign_keys=ON un ID fantasma
    # alzerebbe IntegrityError e annullerebbe tutta la transazione del context.
    sql_ordine_exists = """
    SELECT 1 FROM ordini WHERE id_ordine = ? LIMIT 1;
    """

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # id_ordine sicuro per FK: None / "" / ID assente in ordini → NULL.
        # Non inventiamo ID: se A2 non ha trovato l'ordine, la colonna resta NULL
        # e l'operatore può comunque leggere risposta + telemetria.
        id_ordine_fk: str | None = None
        if id_ordine is not None:
            id_candidato = str(id_ordine).strip()
            if id_candidato:
                cursor.execute(sql_ordine_exists, (id_candidato,))
                if cursor.fetchone() is not None:
                    id_ordine_fk = id_candidato
                else:
                    # Diagnostica a terminale (niente logger su file): così
                    # in demo si vede perché id_ordine è NULL nonostante A2
                    # abbia proposto un codice.
                    print(
                        "[DB] WARNING: id_ordine="
                        f"{id_candidato!r} assente in ordini → "
                        "final_response.id_ordine=NULL (FK)."
                    )

        cursor.execute(
            sql_insert_final,
            (
                id_ordine_fk,
                email_norm,
                risposta_generata,
                priorita_ticket,
                int(token_input),
                int(token_output),
                float(costo_calcolato),
                float(latenza_secondi),
            ),
        )
        # lastrowid = id_risposta appena creato (INTEGER PRIMARY KEY AUTOINCREMENT).
        return int(cursor.lastrowid)


# =====================================================================
# WORKFLOW HITL (STEP 5): ordini, congelamento, resume
# =====================================================================

def get_ordine_importo(id_ordine: str) -> float | None:
    """Legge l'importo EUR di un ordine per la soglia di rimborso (100€).

    Usata dal breakpoint su ``issue_refund``: se l'ordine non esiste restituisce
    ``None`` (observation errore lato Resolver), altrimenti un ``float`` per il
    confronto con ``SOGLIA_RIMBORSO_EUR`` in ``logic.py``.

    Args:
        id_ordine: Chiave primaria in ``ordini`` (es. ``ORD-404-REFUND-HIGH``).

    Returns:
        Importo come float, oppure ``None`` se ID assente o stringa vuota.
    """
    id_candidato = (id_ordine or "").strip()
    if not id_candidato:
        return None

    sql_select_importo = """
    SELECT importo FROM ordini WHERE id_ordine = ? LIMIT 1;
    """

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql_select_importo, (id_candidato,))
        row = cursor.fetchone()
        if row is None:
            return None
        # SQLite può restituire DECIMAL come str/float; normalizziamo a float
        # per confronti numerici stabili con la soglia HITL.
        return float(row[0])


def save_workflow_pending(
    *,
    id_sessione: str,
    email_cliente: str,
    messaggi: list[dict[str, Any]],
    id_ordine: str | None = None,
) -> None:
    """Congela il Resolver: INSERT OR REPLACE su ``workflow_states``.

    Serializza la cronologia OpenAI **dopo** l'assistant con ``tool_calls`` su
    ``issue_refund`` e **prima** dell'observation ``role=tool`` (stato esatto
    del breakpoint). Lo stato workflow è sempre ``PENDING_APPROVAL``.

    ``id_ordine`` viene scritto solo se presente in ``ordini``: la FK
    ``workflow_states.id_ordine → ordini(id_ordine)`` altrimenti farebbe
    fallire la transazione con ``PRAGMA foreign_keys=ON``.

    Args:
        id_sessione: Chiave primaria (es. ``SESS-`` + uuid hex).
        email_cliente: Mittente da hand-off A1.
        messaggi: Lista messaggi Resolver da ``json.dumps`` in ``messaggi_serializzati``.
        id_ordine: ID proposto dal tool call; ``None`` o assente in DB → colonna NULL.
    """
    sessione_norm = (id_sessione or "").strip()
    if not sessione_norm:
        raise ValueError("id_sessione obbligatorio per save_workflow_pending")

    email_norm = (email_cliente or "").strip() or _EMAIL_CLIENTE_FALLBACK

    # default=str: tool_call id e campi non-JSON-serializzabili non bloccano il freeze.
    messaggi_json = json.dumps(messaggi, ensure_ascii=False, default=str)

    sql_ordine_exists = """
    SELECT 1 FROM ordini WHERE id_ordine = ? LIMIT 1;
    """

    sql_upsert_workflow = """
    INSERT OR REPLACE INTO workflow_states (
        id_sessione,
        email_cliente,
        id_ordine,
        stato_workflow,
        messaggi_serializzati
    )
    VALUES (?, ?, ?, 'PENDING_APPROVAL', ?);
    """

    with get_db_connection() as conn:
        cursor = conn.cursor()

        id_ordine_fk: str | None = None
        if id_ordine is not None:
            id_candidato = str(id_ordine).strip()
            if id_candidato:
                cursor.execute(sql_ordine_exists, (id_candidato,))
                if cursor.fetchone() is not None:
                    id_ordine_fk = id_candidato
                else:
                    print(
                        "[DB] WARNING: id_ordine="
                        f"{id_candidato!r} assente in ordini → "
                        "workflow_states.id_ordine=NULL (FK)."
                    )

        cursor.execute(
            sql_upsert_workflow,
            (sessione_norm, email_norm, id_ordine_fk, messaggi_json),
        )


def load_workflow_state(id_sessione: str) -> dict[str, Any] | None:
    """Carica una riga ``workflow_states`` per il resume HITL.

    Restituisce un dict con le colonne della tabella; ``messaggi_serializzati``
    resta stringa JSON (``logic.py`` fa ``json.loads`` quando ripristina la cronologia).

    Args:
        id_sessione: Chiave primaria della sessione congelata.

    Returns:
        Dict con chiavi ``id_sessione``, ``email_cliente``, ``id_ordine``,
        ``stato_workflow``, ``messaggi_serializzati``, ``data_congelamento``;
        ``None`` se la sessione non esiste.
    """
    sessione_norm = (id_sessione or "").strip()
    if not sessione_norm:
        return None

    sql_load_workflow = """
    SELECT
        id_sessione,
        email_cliente,
        id_ordine,
        stato_workflow,
        messaggi_serializzati,
        data_congelamento
    FROM workflow_states
    WHERE id_sessione = ?
    LIMIT 1;
    """

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql_load_workflow, (sessione_norm,))
        row = cursor.fetchone()
        if row is None:
            return None

        return {
            "id_sessione": row[0],
            "email_cliente": row[1],
            "id_ordine": row[2],
            "stato_workflow": row[3],
            "messaggi_serializzati": row[4],
            "data_congelamento": row[5],
        }

        """ E' stato preferito l'unpacking per indici per poter ritornare direttamente il json,
        altrimenti avrei dovuto appoggiare i valori in delle variabili provvisorie e
        poi rimapparle sul json (vedi sotto)
        
        Unpacking diretto:
            (
                id_sess,
                email_cli,
                id_ord,
                stato_wf,
                msg_ser,
                data_cong,
            ) = row

            return {
                "id_sessione": id_sess,
                "email_cliente": email_cli,
                ...
            }
        """


def mark_workflow_resumed(id_sessione: str) -> bool:
    """Segna il workflow come concluso dopo un resume riuscito.

    Aggiorna ``stato_workflow`` a ``APPROVED`` (la riga resta per audit didattico;
    non cancelliamo la sessione). Se l'ID non esiste, non solleva eccezione.

    Args:
        id_sessione: Sessione appena ripresa da ``resume_hitl_workflow``.

    Returns:
        ``True`` se almeno una riga è stata aggiornata, ``False`` altrimenti.
    """
    sessione_norm = (id_sessione or "").strip()
    if not sessione_norm:
        return False

    sql_mark_approved = """
    UPDATE workflow_states
    SET stato_workflow = 'APPROVED'
    WHERE id_sessione = ?;
    """

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql_mark_approved, (sessione_norm,))
        return cursor.rowcount > 0


# =====================================================================
# FUNZIONE DI INIZIALIZZAZIONE
# =====================================================================

def init_db() -> None:
    """
    Inizializza il database creando tutte le tabelle necessarie 
    se non sono già presenti.
    """
    queries = [
        SQL_CREATE_ORDINI_TABLE,
        SQL_CREATE_ORDINI_INDEX,
        SQL_CREATE_WORKFLOW_STATES_TABLE,
        SQL_CREATE_SECURITY_AUDIT_TABLE,
        SQL_CREATE_FINAL_RESPONSE_TABLE,
        SQL_CREATE_POLICY_INDEX_META_TABLE,
        SQL_CREATE_POLICY_CHUNKS_TABLE,
        SQL_CREATE_POLICY_CHUNKS_HASH_INDEX,
    ]
    
    print(f"Inizializzazione del database in corso presso: {DB_PATH}...")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for query in queries:
            cursor.execute(query)

        # AGGIORNAMENTO: Richiamiamo la funzione di seed all'interno della stessa transazione
        seed_db(conn)
            
    print("Database inizializzato con successo!")