# src/bootstrap.py
import os
import sys
from src.config import DB_PATH, OPENAI_API_KEY  # Ipotizzando la gestione centralizzata
from src.database import init_db

def check_environment() -> None:
    """
    Verifica che tutte le variabili d'ambiente necessarie siano caricate.
    """
    print("1. Verifica delle variabili d'ambiente...")
    if not OPENAI_API_KEY:
        print("[-] ERRORE CRITICO: La variabile OPENAI_API_KEY non è configurata nel file .env!")
        sys.exit(1)
    print("[+] Variabili d'ambiente verificate con successo.")

def check_required_files() -> None:
    """
    Verifica la presenza dei file fisici richiesti dal sistema (DB folder, Policy RAG).
    """
    print("2. Verifica dei file richiesti...")
    
    # Assicura la presenza della cartella data/
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    
    # Verifica che esista il file per il RAG (STEP 1 del PDF)
    policy_path = os.path.join(os.path.dirname(db_dir), "data", "policy_supporto.txt")
    if not os.path.exists(policy_path):
        print(f"[-] WARNING: Il file delle policy '{policy_path}' non esiste!")
        print("    Assicurati di crearlo e popolarlo prima di avviare il RAG.")
    else:
        print("[+] File delle policy rilevato.")

def seed_database_if_empty() -> None:
    """
    Inserisce dati di test (es. ordini fake) se il database è appena stato creato.
    """
    print("4. Controllo seed del database...")
    # Qui potrai importare funzioni da src/database per inserire ordini di test
    # (Ad esempio, per lo STEP 5 ti servirà un ordine > 100€ per testare il breakpoint)
    pass

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
        
        # 3. Inizializzazione del DB (richiama la tua funzione init_db)
        print("3. Inizializzazione del database...")
        init_db()
        
        seed_database_if_empty()
        
        print("=" * 50)
        print("[+] BOOTSTRAP COMPLETATO CON SUCCESSO! Il sistema è pronto.")
        print("=" * 50 + "\n")
        
    except Exception as e:
        print(f"[-] ERRORE CRITICO DURANTE IL BOOTSTRAP: {e}")
        sys.exit(1)