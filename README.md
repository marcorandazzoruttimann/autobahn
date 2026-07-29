# Autobahn — Customer Care agentico (progetto didattico)

Pipeline di **triage**, **RAG** su policy aziendali e **resolver** ReAct per email di supporto clienti. Include **guardrail** deterministico (nessun LLM), **HITL** su rimborsi sopra soglia e persistenza su **SQLite**.

Il codice è pensato per lo studio: commenti estesi, scenari demo in `src/main.py` e documentazione architetturale in [`docs/`](docs/README.md).

## Requisiti

- **Python 3.10+**
- Chiave API **OpenAI** (gli agenti A1 Triage e A2 Resolver la usano; il guardrail no)
- Connessione internet al primo avvio (embeddings policy e chiamate modello)

## Installazione

Dalla **root del repository** (importante per import `src.*` e `test.seed`):

```bash
git clone <URL-del-repo> autobahn
cd autobahn

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e .
```

Per strumenti di sviluppo opzionali:

```bash
pip install -e ".[dev]"
```

## Configurazione

Crea un file `.env` nella root (non è versionato su Git). Esempio minimo:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-nano

# Opzionali (default in src/config.py se omessi)
# NONCE_START=[SECURE_DATA_BOUNDARY_START_DEFAULT]
# NONCE_END=[SECURE_DATA_BOUNDARY_END_DEFAULT]
# AGENTIC_LOG_PATH=logs/agentic.log
```

Senza `OPENAI_API_KEY` il bootstrap termina con errore esplicito (`src/bootstrap.py`).

## Avvio rapido

```bash
# Dalla root, con venv attivo
python -m src.main
```

All’avvio succede in automatico:

1. Verifica configurazione e cartelle (`data/`, `logs/`)
2. Creazione/aggiornamento schema SQLite e **seed** demo (`test/seed.py`)
3. Warm dell’indice embeddings della policy (`data/policy_supporto.txt`)
4. Esecuzione degli scenari definiti in `_SCENARI_DEMO` dentro [`src/main.py`](src/main.py)

### Resume HITL (supervisore simulato)

Dopo uno scenario con rimborso **> 100€**, oppure usando la sessione pre-seed:

```bash
python -m src.main --resume SESS-TEST-RESUME-01
```

Salta guardrail e triage; completa il `issue_refund` pendente e scrive `final_response`.

## Scenari demo

| # | Tema | Esito atteso (se il flusso va a buon fine) |
|---|------|---------------------------------------------|
| 1 | Ordine OK (`ORD-999-OK`) | Path felice — *opzionale in main* (può essere commentato nella lista) |
| 2 | Ordine smarrito (`ORD-101-LOST`) | A2 usa tool + policy RAG |
| 3 | Prompt injection | `ATTACK_BLOCKED`, nessuna chiamata LLM |
| 4 | Rimborso alto 250€ (`ORD-404-REFUND-HIGH`) | Freeze `PENDING_APPROVAL` se A2 chiama `issue_refund` |
| 5 | Rimborso 35€ (`ORD-302-REFUND-LOW`) | `issue_refund` sotto soglia → ticket chiuso in DB |

Gli scenari **4** e **5** dipendono dal fatto che il modello invochi `issue_refund`; in caso di esito diverso, ripeti il run o controlla i log `[RESOLVER]`.

## Struttura del progetto

```text
autobahn/
├── src/           # Codice applicativo (main, logic, guardrail, RAG, tools, DB)
├── test/          # Seed SQLite per demo e test (package locale `test`, non pytest suite)
├── data/          # DB SQLite, policy RAG, artefatti runtime
├── docs/          # Guide architetturali (flowchart Mermaid, HITL, telemetria)
├── pyproject.toml # Dipendenze e metadati pacchetto
└── README.md      # Questo file
```

Database principale: `data/customer_db.db` (creato/aggiornato al bootstrap).

## Documentazione approfondita

Ordine consigliato: [docs/README.md](docs/README.md) → capitoli `01`–`07` (overview, bootstrap, guardrail, agenti, RAG, HITL, persistenza).

## Risoluzione problemi

| Problema | Cosa controllare |
|----------|------------------|
| `ModuleNotFoundError: test.seed` | Esegui comandi dalla **root** del repo, non `python src/main.py` |
| Errore API OpenAI | `.env`, credito account, modello in `OPENAI_MODEL` |
| Seed / resume non trovato | Rilancia `python -m src.main` una volta (bootstrap rifà il seed) |

## Licenza e uso

Progetto didattico; verifica eventuale licenza nel repository prima di redistribuire o usarlo in produzione.
