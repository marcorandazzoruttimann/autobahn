# src/bootstrap.py (Versione Aggiornata)
import sys

from src.paths import POLICY_PATH, ensure_directories_exist
from src.database import init_db
from src.rag.policy_semantic import warm_policy_index_from_file
from src.config import OPENAI_API_KEY, AGENTIC_LOG_PATH, get_config_summary


def check_environment() -> None:
    print("1. Verifica delle variabili d'ambiente e configurazioni...")
    if not OPENAI_API_KEY:
        print("[-] ERRORE CRITICO: La chiave OPENAI_API_KEY non è configurata nel file .env!")
        sys.exit(1)

    summary = get_config_summary()
    print(f"    [+] Modello AI configurato: {summary['OPENAI_MODEL']}")
    print(f"    [+] API Key caricata: {summary['OPENAI_API_KEY']}")
    print(f"    [+] Nonce di sicurezza attivo: {summary['NONCE_START'][:15]}...")


def check_required_files() -> None:
    print("2. Verifica dei file e delle cartelle richieste...")

    ensure_directories_exist()
    AGENTIC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"    [+] Directory log verificata: {AGENTIC_LOG_PATH.parent}")

    if not POLICY_PATH.exists():
        print(f"[-] WARNING: Il file delle policy '{POLICY_PATH}' non esiste!")
    else:
        print("    [+] File delle policy rilevato.")


def warm_policy_index() -> None:
    print("4. Verifica indice policy SQLite...")
    if not POLICY_PATH.exists():
        print("    [-] SKIP: file policy assente.")
        return
    try:
        warm_policy_index_from_file(POLICY_PATH)
        print("    [+] Policy index SQLite verificato e pronto.")
    except Exception as e:
        print(f"[-] WARNING: Errore durante il check a caldo dell'indice policy: {e}")


def run_bootstrap() -> None:
    """Esegue l'intera sequenza di startup del sistema."""
    print("=" * 50)
    print("AVVIO SEQUENZA DI BOOTSTRAP - AUTOBAHN SYSTEM")
    print("=" * 50)

    try:
        check_environment()
        check_required_files()

        print("3. Inizializzazione del database...")
        init_db()

        warm_policy_index()

        print("=" * 50)
        print("[+] BOOTSTRAP COMPLETATO CON SUCCESSO! Il sistema è pronto.")
        print("=" * 50 + "\n")

    except Exception as e:
        print(f"[-] ERRORE CRITICO DURANTE IL BOOTSTRAP: {e}")
        sys.exit(1)
