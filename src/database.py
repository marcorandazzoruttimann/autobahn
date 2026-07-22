import sqlite3
from typing import Generator
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