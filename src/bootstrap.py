# src/bootstrap.py (Versione Aggiornata)
import sys

# Importiamo i percorsi centralizzati
from src.paths import DB_PATH, POLICY_PATH, ensure_directories_exist
from src.database import init_db

# AGGIORNAMENTO: Importiamo le variabili e la funzione di diagnostica da config.py
from src.config import OPENAI_API_KEY, AGENTIC_LOG_PATH, get_config_summary

def check_environment() -> None:
    print("1. Verifica delle variabili d'ambiente e configurazioni...")
    if not OPENAI_API_KEY:
        print("[-] ERRORE CRITICO: La chiave OPENAI_API_KEY non è configurata nel file .env!")
        sys.exit(1)
        
    # AGGIORNAMENTO: Mostriamo un riepilogo pulito e mascherato all'avvio
    summary = get_config_summary()
    print(f"    [+] Modello AI configurato: {summary['OPENAI_MODEL']}")
    print(f"    [+] API Key caricata: {summary['OPENAI_API_KEY']}")
    print(f"    [+] Nonce di sicurezza attivo: {summary['NONCE_START'][:15]}...")

def check_required_files() -> None:
    print("2. Verifica dei file e delle cartelle richieste...")
    
    # Crea le cartelle fondamentali di progetto (data/)
    ensure_directories_exist()
    
    # AGGIORNAMENTO: Assicuriamoci che esista anche la cartella per i log se specificata
    # Peculiarità Python: .parent su un oggetto Path restituisce la cartella che contiene il file.
    # .mkdir(exist_ok=True) la crea solo se non è già presente.
    AGENTIC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"    [+] Directory log verificata: {AGENTIC_LOG_PATH.parent}")
    
    if not POLICY_PATH.exists():
        print(f"[-] WARNING: Il file delle policy '{POLICY_PATH}' non esiste!")
        print("    Assicurati di crearlo e popolarlo prima di avviare il RAG.")
    else:
        print("    [+] File delle policy rilevato.")

def run_bootstrap() -> None:
    """
    Esegue l'intera sequenza di startup del sistema.
    """
    print("=" * 50)
    print("AVVIO SEQUENZA DI BOOTSTRAP - AUTOBAHN SYSTEM")
    print("=" * 50)
    
    try:
        check_environment()
        check_required_files()
        
        print("3. Inizializzazione del database...")
        init_db()
        
        print("=" * 50)
        print("[+] BOOTSTRAP COMPLETATO CON SUCCESSO! Il sistema è pronto.")
        print("=" * 50 + "\n")
        
    except Exception as e:
        print(f"[-] ERRORE CRITICO DURANTE IL BOOTSTRAP: {e}")
        sys.exit(1)