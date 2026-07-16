import os
import sqlite3
from typing import Generator
from contextlib import contextmanager
from src.config import DB_PATH  # Immaginando che config.py gestisca i percorsi

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


# =====================================================================
# GESTIONE CONNESSIONE (Context Manager)
# =====================================================================

@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager per gestire in sicurezza l'apertura e la chiusura 
    della connessione al database SQLite, garantendo il rollback in caso di errore.
    """
    # Assicuriamoci che la cartella 'data/' esista prima di connetterci
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    # Abilitiamo il supporto alle Foreign Key (disattivato di default in SQLite)
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
        SQL_CREATE_FINAL_RESPONSE_TABLE
    ]
    
    print(f"Inizializzazione del database in corso presso: {DB_PATH}...")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for query in queries:
            cursor.execute(query)
            
    print("Database inizializzato con successo!")