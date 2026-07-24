"""Eccezioni di dominio per il triage / resolver Autobahn."""

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


class ResolverError(TriageError):
    """Errore nell'Agente 2 Resolver (JSON finale malformato, cap turni, ecc.).

    Estende ``TriageError`` così l'orchestratore può catturare entrambi con un
    solo ``except TriageError`` se vuole interrompere l'intera pipeline.
    """
