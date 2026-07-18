"""
Modulo per la gestione centralizzata delle configurazioni e delle variabili d'ambiente.
Carica le variabili dal file '.env' sfruttando 'python-dotenv' e le espone come costanti tipizzate.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Importiamo i percorsi centralizzati da paths.py per mantenere l'allineamento
from src.paths import ENV_PATH, ROOT_DIR

# =====================================================================
# CARICAMENTO DEL FILE .ENV
# =====================================================================

# Peculiarità Python: load_dotenv() cerca di default il file .env nella directory corrente.
# Passando esplicitamente 'dotenv_path=ENV_PATH' (un oggetto Path), forziamo il caricamento
# dal percorso assoluto calcolato in paths.py, evitando fallimenti se eseguiamo gli script
# da sotto-cartelle.
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    # Fail-safe non bloccante in fase di importazione, ma utile per lo sviluppatore
    print(f"[!] WARNING: File .env non trovato in {ENV_PATH}. Verranno usate le variabili di sistema.")

# =====================================================================
# ESPOSIZIONE DELLE VARIABILI D'AMBIENTE COME COSTANTI TIPIZZATE
# =====================================================================

# 1. Configurazione API OpenAI
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
#OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4.1-nano")

# 2. Stringhe di Confine Sicuro (Nonce per mitigazione Prompt Injection/Delimitatori)
NONCE_START: str = os.getenv("NONCE_START", "[SECURE_DATA_BOUNDARY_START_DEFAULT]")
NONCE_END: str = os.getenv("NONCE_END", "[SECURE_DATA_BOUNDARY_END_DEFAULT]")

# 3. Gestione opzionale dei Log su File (Incrocio con la tua configurazione .env)
# Peculiarità Python: Recuperiamo il path relativo dal .env (es. 'logs/agentic.log')
# e lo convertiamo in un oggetto Path assoluto agganciandolo a ROOT_DIR.
_log_path_str: str = os.getenv("AGENTIC_LOG_PATH", "logs/agentic.log")
AGENTIC_LOG_PATH: Path = ROOT_DIR / _log_path_str


# =====================================================================
# DIAGNOSTICA RAPIDA (Per debug in fase di Bootstrap)
# =====================================================================

def get_config_summary() -> dict:
    """
    Restituisce un dizionario contenente un riepilogo sicuro delle configurazioni caricate.
    Le chiavi sensibili vengono mascherate.
    """
    # Peculiarità Python: Operatore ternario per mascherare parzialmente la chiave API
    masked_key = f"{OPENAI_API_KEY[:8]}...{OPENAI_API_KEY[-4:]}" if len(OPENAI_API_KEY) > 12 else "NON CONFIGURATA"
    
    return {
        "OPENAI_MODEL": OPENAI_MODEL,
        "OPENAI_API_KEY": masked_key,
        "NONCE_START": NONCE_START,
        "NONCE_END": NONCE_END,
        "AGENTIC_LOG_PATH": str(AGENTIC_LOG_PATH)
    }