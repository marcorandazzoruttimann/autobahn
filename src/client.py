"""
Client OpenAI: connessione e configurazione centralizzata.
Implementa il riutilizzo dell'istanza (Singleton/Cached) per mantenere
i pool di connessione TCP aperti ed efficienti per tutte le chiamate successive.
"""

from openai import OpenAI
from src.config import OPENAI_API_KEY, OPENAI_MODEL

MODEL = OPENAI_MODEL

# Peculiarità Python: Variabile privata a livello di modulo che fungerà da 
# cache per la nostra istanza unica del client.
_client_instance: OpenAI | None = None


def get_client() -> OpenAI:
    """
    Restituisce l'istanza globale del client OpenAI.
    Se non esiste ancora, la crea; altrimenti restituisce quella già attiva,
    mantenendo la connessione sempre aperta e disponibile.
    """
    global _client_instance

    # Se l'istanza non è ancora stata creata, la inizializziamo una sola volta
    if _client_instance is None:
        if not OPENAI_API_KEY or not OPENAI_API_KEY.strip():
            raise ValueError(
                "API key non trovata o non configurata. "
                "Assicurati che OPENAI_API_KEY sia presente nel file .env."
            )
        
        # Sotto il cofano, l'inizializzazione di OpenAI() crea un oggetto 'httpx.Client'.
        # Questo oggetto gestisce internamente un HTTP Connection Pool.
        _client_instance = OpenAI(api_key=OPENAI_API_KEY.strip())
        print("    [+] Client OpenAI istanziato e pool di connessioni allocato.")

    # Restituiamo l'istanza esistente senza ricrearla
    return _client_instance
    