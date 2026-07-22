"""Eccezioni di dominio per il triage Autobahn."""

from __future__ import annotations


class TriageError(Exception):
    """Errore generico nel flusso di triage (base per eccezioni più specifiche)."""


class SecurityGuardrailError(TriageError):
    """Input bloccato dal guardrail di sicurezza prima dell'elaborazione LLM.

    L'orchestratore intercetta questa eccezione per interrompere il flusso e
    usare direttamente ``ticket`` (stato ``ATTACK_BLOCKED``, priorità ``CRITICAL``,
    excerpt, vettori, id audit, ecc.) senza dipendere da un contesto di sessione.
    """

    def __init__(self, message: str, *, ticket: dict) -> None:
        super().__init__(message)
        # Payload serializzabile costruito da guardrails.py al momento del blocco.
        self.ticket = ticket
