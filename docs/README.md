# Documentazione architetturale Autobahn

Cartella dedicata ai file Markdown di studio: flowchart, sottoflussi e note didattiche.
Il codice vive in `src/` e `test/`; qui si spiega **come e perché** i pezzi si collegano.

## Come leggere

Ordine consigliato (dal generale al particolare):

| # | File | Contenuto |
|---|------|-----------|
| 1 | [01-overview-flowchart.md](01-overview-flowchart.md) | Mappa end-to-end + comandi demo |
| 2 | [02-bootstrap-e-seed.md](02-bootstrap-e-seed.md) | Avvio sistema, DB, seed, warm RAG |
| 3 | [03-guardrail.md](03-guardrail.md) | Blocco injection prima di qualsiasi LLM |
| 4 | [04-triage-e-resolver.md](04-triage-e-resolver.md) | Agenti A1/A2, hand-off, loop ReAct |
| 5 | [05-rag-embeddings.md](05-rag-embeddings.md) | Policy, hash, embeddings, cosine |
| 6 | [06-hitl-resume.md](06-hitl-resume.md) | Soglia 100€, freeze, `--resume` |
| 7 | [07-persistenza-telemetria.md](07-persistenza-telemetria.md) | Tabelle SQLite, token, latenza |
| — | [appunti.md](appunti.md) | Spazio libero per le tue note |

Anteprima Mermaid: in Cursor apri il file `.md` e usa la preview Markdown; i blocchi ` ```mermaid ` diventano diagrammi.

## Comandi demo (entry-point)

```bash
# Pipeline sugli scenari configurati in src/main.py
python -m src.main

# Ripresa HITL della sessione seed (dopo bootstrap/seed)
python -m src.main --resume SESS-TEST-RESUME-01
```

> **Nota didattica:** lanciare i moduli dalla **root del repo** (o con `PYTHONPATH` sulla root), così importano sia `src.*` sia `test.seed`. Eseguire un singolo file sotto `src/` come script può far fallire `from test.seed` (conflitto col package `test` della stdlib).

## Come aggiungere note (convenzioni Markdown)

Markdown è testo semplice. Per questo progetto usiamo tre pattern:

### 1. Callout didattico (visibile in preview)

```markdown
> **Nota didattica:** spiegazione del *perché*, non solo del *cosa*.
```

Usalo dentro i file `01`–`07` quando vuoi arricchire un passaggio senza riscrivere il flowchart.

### 2. Sezione “Approfondisci”

Alla fine di ogni capitolo c’è (o puoi aggiungere) una lista di domande/esercizi. È il posto giusto per collegare teoria e codice.

### 3. File `appunti.md`

Per note personali, dubbi, screenshot testuali, bozze: scrivi lì. Non mescolare appunti grezzi nei flowchart “ufficiali”, così la mappa resta leggibile.

Esempio di voce in `appunti.md`:

```markdown
## 2026-07-28 — Primo run HITL

- Comando usato: `python -m src.main --resume SESS-TEST-RESUME-01`
- Osservazione: ...
```

## Cosa non mettere qui

- Plan interni di Cursor (restano in `.cursor/plans/`)
- Copia-incolla interi file Python (meglio link al path + spiegazione)
- Build HTML/PDF automatiche: per lo studio bastano i `.md` nel repo
