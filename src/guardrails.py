"""Guardrail di ingresso STEP 2 — blocca prompt injection prima degli agenti LLM.

Pipeline deterministica (nessun LLM):
  testo email → scan regex → se malevolo: audit SQLite + ticket ATTACK_BLOCKED + raise.
  Se sicuro: return True (l'orchestratore può proseguire verso Triage).
"""

from __future__ import annotations

from src.database import insert_security_audit
from src.errors import SecurityGuardrailError
from src.input_guardrail import (
    AttackVector,
    GuardrailResult,
    PatternMatch,
    input_excerpt,
    scan_ticket_input,
)

# Priorità di etichetta per ``categoria_attacco`` quando più vettori matchano
# nello stesso testo. Più alto = più specifico/grave per l'operatore in audit.
# DIRECT_INJECTION collassa su PROMPT_INJECTION (default schema DB) perché è
# la famiglia generica di "ignora le istruzioni" senza hijack di tool/policy.
_CATEGORIA_PRIORITA: dict[AttackVector, int] = {
    AttackVector.TOOL_HIJACK: 50,
    AttackVector.POLICY_OVERRIDE: 40,
    AttackVector.LOG_SUPPRESSION: 30,
    AttackVector.ROLE_OVERRIDE: 20,
    AttackVector.DIRECT_INJECTION: 10,
}

_CATEGORIA_LABEL: dict[AttackVector, str] = {
    AttackVector.TOOL_HIJACK: "TOOL_HIJACK",
    AttackVector.POLICY_OVERRIDE: "POLICY_OVERRIDE",
    AttackVector.LOG_SUPPRESSION: "LOG_SUPPRESSION",
    AttackVector.ROLE_OVERRIDE: "ROLE_OVERRIDE",
    # Allineato al DEFAULT della colonna security_audit.categoria_attacco
    AttackVector.DIRECT_INJECTION: "PROMPT_INJECTION",
}


def _categoria_da_vettori(matches: list[PatternMatch]) -> str:
    """Sceglie una sola etichetta audit a partire dai match dello scanner.

    La tabella ``security_audit`` ha una sola colonna ``categoria_attacco``:
    non possiamo persistere N vettori. Prendiamo il vettore con priorità
    più alta (tool hijack > policy override > …), così l'operatore vede
    subito la minaccia più operativa.
    """
    if not matches:
        return "PROMPT_INJECTION"

    # max su chiave numerica: evita confronti lessicografici sui nomi Enum
    peggiore = max(matches, key=lambda m: _CATEGORIA_PRIORITA.get(m.vector, 0))
    return _CATEGORIA_LABEL.get(peggiore.vector, "PROMPT_INJECTION")


def _build_blocked_ticket(
    testo: str,
    result: GuardrailResult,
    *,
    id_audit: int,
    categoria: str,
) -> dict:
    """Costruisce il dict ticket da allegare a ``SecurityGuardrailError``.

    L'orchestratore (STEP 3+) cattura l'eccezione e usa questo payload al
    posto di una risposta LLM: stato ATTACK_BLOCKED, priorità massima,
    excerpt e metadati per UI/print senza rieseguire lo scan.
    """
    # Serializziamo i PatternMatch (dataclass frozen) in tipi JSON-friendly:
    # Enum → .value, così print/log non dipendono da oggetti Python.
    vectors = sorted({m.vector.value for m in result.matches})
    matched_patterns = [m.pattern for m in result.matches]

    return {
        "stato_ticket": "ATTACK_BLOCKED",
        # Priorità di business del ticket (non confondere con result.severity
        # che è la severità tecnica dello scan HIGH/CRITICAL/…).
        "priorita": "CRITICAL",
        "severity": result.severity,
        "categoria_attacco": categoria,
        "vectors": vectors,
        "matched_patterns": matched_patterns,
        # Excerpt corto: evita di riverberare payload di injection interi
        # nei print a terminale (il testo pieno resta in security_audit).
        "input_excerpt": input_excerpt(testo),
        "id_audit": id_audit,
    }


def sanitize_email_input(testo: str) -> bool:
    """Verifica che il testo email sia sicuro prima di passarlo agli agenti.

    Returns:
        ``True`` se nessuno dei pattern di attacco ha matchato.

    Raises:
        SecurityGuardrailError: input malevolo; ``exc.ticket`` contiene lo
            snapshot ATTACK_BLOCKED (già persistito su ``security_audit``).
    """
    # 1) Scan deterministico: solo regex, zero chiamate LLM / DB lettura.
    result = scan_ticket_input(testo)

    if result.allowed:
        print("[GUARDRAIL] Input sicuro: nessun vettore di attacco rilevato.")
        return True

    # 2) Path di blocco: prima persistiamo l'audit, poi costruiamo il ticket.
    # Ordine voluto: se INSERT fallisce non solleviamo un ticket "fantasma"
    # senza id_audit correlabile dall'operatore.
    categoria = _categoria_da_vettori(result.matches)
    id_audit = insert_security_audit(
        input_testo=testo,
        # email_cliente=None: a questo step non abbiamo ancora il Triage
        # che estrae il mittente; la riga resta comunque tracciabile via id_audit.
        email_cliente=None,
        categoria_attacco=categoria,
        stato_ticket="ATTACK_BLOCKED",
    )

    ticket = _build_blocked_ticket(
        testo,
        result,
        id_audit=id_audit,
        categoria=categoria,
    )

    # 3) Feedback operativo a terminale (niente logger su file — solo print + DB).
    print(
        "[GUARDRAIL] ATTACK_BLOCKED | "
        f"categoria={categoria} | severita={result.severity} | "
        f"id_audit={id_audit} | excerpt={ticket['input_excerpt']!r}"
    )

    # 4) Interrompe il flusso: il bool True non viene mai restituito qui.
    raise SecurityGuardrailError(
        f"Input bloccato dal guardrail ({categoria}, severita={result.severity})",
        ticket=ticket,
    )
