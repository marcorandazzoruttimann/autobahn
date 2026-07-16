# src/main.py
from src.bootstrap import run_bootstrap

def main():
    # Esegui il bootstrap come primissima istruzione
    run_bootstrap()
    
    # Da qui in poi il sistema è configurato e pronto
    print("Avvio del loop di simulazione del Customer Care...")
    
    # Esempio:
    # email_fittizia = "ciao, vorrei un rimborso per l'ordine #123..."
    # risultato = orchestratore.elabora(email_fittizia)

if __name__ == "__main__":
    main()