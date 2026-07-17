"""
Modulo per la gestione centralizzata e robusta dei percorsi (Paths) del progetto.
Utilizza la libreria moderna 'pathlib' al posto del vecchio 'os.path',
garantendo la compatibilità cross-platform (Windows, macOS, Linux).
"""

from pathlib import Path

# =====================================================================
# DETERMINAZIONE DELLE CARTELLE CHIAVE (BASE DIRECTORY)
# =====================================================================

# Peculiarità Python: '__file__' è una variabile speciale (dunder variable) 
# popolata automaticamente dall'interprete con il percorso assoluto del file corrente.
# .resolve() risolve eventuali link simbolici, restituendo il path reale assoluto.
# .parent prende la directory genitore. Essendo in 'src/paths.py':
#   - Il primo .parent restituisce la cartella 'src/'
#   - Il secondo .parent restituisce la cartella radice del progetto 'autobahn-system/'
SRC_DIR: Path = Path(__file__).resolve().parent
ROOT_DIR: Path = SRC_DIR.parent

# =====================================================================
# DEFINIZIONE DEI PERCORSI DEI FILE E DELLE CARTELLE (STRUTTURA MINIMA)
# =====================================================================

# 1. Cartella dati di sistema (data/)
# Peculiarità Python (Pathlib): L'operatore '/' è stato sovraccaricato (overloaded) 
# nella classe Path. Non effettua una divisione matematica, ma concatena i percorsi 
# in modo sicuro, gestendo automaticamente i diversi tipi di slash (/ su Unix, \ su Windows).
DATA_DIR: Path = ROOT_DIR / "data"

# 2. Database SQLite (customer_db.db) - STEP 1 del PDF
DB_PATH: Path = DATA_DIR / "customer_db.db"

# 3. File delle policy aziendali (policy_supporto.txt) - STEP 1 del PDF
POLICY_PATH: Path = DATA_DIR / "policy_supporto.txt"

# 4. File di configurazione ambientale (.env) nella root del progetto
ENV_PATH: Path = ROOT_DIR / ".env"


# =====================================================================
# FUNZIONI DI UTILITY PER IL BOOTSTRAP
# =====================================================================

def ensure_directories_exist() -> None:
    """
    Assicura che tutte le cartelle necessarie per il corretto funzionamento
    dell'applicazione esistano sul disco. Se mancano, le crea.
    """
    # Peculiarità Python: Path.mkdir() lancia FileExistsError se la cartella esiste già.
    # Passando 'exist_ok=True', indichiamo a Python di ignorare l'errore se è già presente.
    # 'parents=True' permette di creare ricorsivamente eventuali cartelle genitore mancanti.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    