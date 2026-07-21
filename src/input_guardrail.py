"""Input Guardrail deterministico — Lezione 18."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class AttackVector(str, Enum):
    DIRECT_INJECTION = "direct_injection"
    POLICY_OVERRIDE = "policy_override"
    TOOL_HIJACK = "tool_hijack"
    LOG_SUPPRESSION = "log_suppression"
    ROLE_OVERRIDE = "role_override"


@dataclass(frozen=True)
class PatternMatch:
    pattern: str
    vector: AttackVector
    severity: Severity


"""@dataclass di sotto è questo equivalente:  "data-class":classe di dati, infatti è una classe di soli dati 
def __init__(self, allowed: bool, matches: list = ..., severity: str = "LOW"):
    self.allowed = allowed
    self.matches = matches
    self.severity = severity
    """

@dataclass
class GuardrailResult: #i seguenti sono parametri input della classe...
    allowed: bool
    matches: list[PatternMatch] = field(default_factory=list)#Utilizzando field(default_factory=list), 
    #dici a Python di creare una lista vuota nuova di zecca ogni volta che crei un oggetto GuardrailResult.
    #simile a matches: list[PatternMatch] = [] ma avresti introdotto il bug del default mutabile. 
    # In Python, le liste passate come argomento di default vengono istanziate una sola volta quando il modulo viene caricato. 
    #Di conseguenza, tutte le istanze di GuardrailResult avrebbero condiviso lo stesso identico oggetto lista in memoria, 
    # mescolando i match di utenti e scenari diversi.
    severity: Severity = "LOW"

    @property
    def highest_severity(self) -> Severity:
        order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        if not self.matches:
            return "LOW"
        return max(self.matches, key=lambda m: order[m.severity]).severity
        """Una lambda è una funzione anonima (senza nome) definita in una riga.
        "Prendi l'oggetto m, leggi la sua proprietà .severity (es. "HIGH"), 
        usala come chiave per cercare nel dizionario order, e restituisci il numero corrispondente (es. 2)."
        """


ATTACK_PATTERNS: tuple[tuple[re.Pattern[str], AttackVector, Severity], ...] = (
    # --- CRITICAL: POLICY OVERRIDE & DIRECT INJECTION ---
    # Italiano
    (re.compile(r"ignora\s+(le\s+)?(istruzioni|policy|regole)", re.I), AttackVector.POLICY_OVERRIDE, "CRITICAL"),
    # Inglese
    (re.compile(r"ignore\s+(all\s+)?(previous\s+)?instructions", re.I), AttackVector.DIRECT_INJECTION, "CRITICAL"),
    # Francese
    (re.compile(r"ignore\s+(les\s+)?(instructions|directives|règles)", re.I), AttackVector.POLICY_OVERRIDE, "CRITICAL"),
    # Spagnolo
    (re.compile(r"ignora\s+(las\s+)?(instrucciones|directrices|reglas)", re.I), AttackVector.POLICY_OVERRIDE, "CRITICAL"),
    # Tedesco
    (re.compile(r"(ignoriere|anweisungen\s+ignorieren|richtlinien\s+ignorieren)", re.I), AttackVector.POLICY_OVERRIDE, "CRITICAL"),

    # --- HIGH / CRITICAL: TOOL HIJACKING ---
    # Italiano
    (re.compile(r"esegui\s+il\s+tool", re.I), AttackVector.TOOL_HIJACK, "CRITICAL"),
    (re.compile(r"chiama\s+isolate_account", re.I), AttackVector.TOOL_HIJACK, "HIGH"),
    (re.compile(r"isolare?\s+l['\u2019]?utente\s+amministratore", re.I), AttackVector.TOOL_HIJACK, "CRITICAL"),
    # Inglese / Internazionale
    (re.compile(r"execute\s+(the\s+)?tool", re.I), AttackVector.TOOL_HIJACK, "CRITICAL"),
    (re.compile(r"call\s+isolate_account", re.I), AttackVector.TOOL_HIJACK, "HIGH"),
    (re.compile(r"isolate\s+(the\s+)?admin(\s+user)?", re.I), AttackVector.TOOL_HIJACK, "CRITICAL"),
    # Francese
    (re.compile(r"exécute\s+(le\s+)?outil", re.I), AttackVector.TOOL_HIJACK, "CRITICAL"),
    (re.compile(r"isoler\s+l['\u2019]?administrateur", re.I), AttackVector.TOOL_HIJACK, "CRITICAL"),
    # Spagnolo
    (re.compile(r"ejecuta\s+(el\s+)?tool|ejecutar\s+(la\s+)?herramienta", re.I), AttackVector.TOOL_HIJACK, "CRITICAL"),
    (re.compile(r"aislar\s+(al\s+)?administrador", re.I), AttackVector.TOOL_HIJACK, "CRITICAL"),
    # Tedesco
    (re.compile(r"tool\s+(ausführen|starten)", re.I), AttackVector.TOOL_HIJACK, "CRITICAL"),
    (re.compile(r"administrator\s+isolieren", re.I), AttackVector.TOOL_HIJACK, "CRITICAL"),

    # --- HIGH: LOG SUPPRESSION ---
    # Italiano
    (re.compile(r"non\s+loggare", re.I), AttackVector.LOG_SUPPRESSION, "HIGH"),
    (re.compile(r"nascondi\s+(le\s+)?tracce", re.I), AttackVector.LOG_SUPPRESSION, "HIGH"),
    # Inglese
    (re.compile(r"do\s+not\s+log|disable\s+logging", re.I), AttackVector.LOG_SUPPRESSION, "HIGH"),
    (re.compile(r"hide\s+(your\s+)?traces|delete\s+logs", re.I), AttackVector.LOG_SUPPRESSION, "HIGH"),
    # Francese
    (re.compile(r"ne\s+pas\s+enregistrer|désactiver\s+les\s+logs", re.I), AttackVector.LOG_SUPPRESSION, "HIGH"),
    (re.compile(r"cache\s+(les\s+)?traces", re.I), AttackVector.LOG_SUPPRESSION, "HIGH"),
    # Spagnolo
    (re.compile(r"no\s+registrar|desactivar\s+logs", re.I), AttackVector.LOG_SUPPRESSION, "HIGH"),
    (re.compile(r"oculta\s+(las\s+)?huellas|borrar\s+logs", re.I), AttackVector.LOG_SUPPRESSION, "HIGH"),
    # Tedesco
    (re.compile(r"nicht\s+protokollieren|logs\s+deaktivieren", re.I), AttackVector.LOG_SUPPRESSION, "HIGH"),
    (re.compile(r"spuren\s+verwischen", re.I), AttackVector.LOG_SUPPRESSION, "HIGH"),

    # --- HIGH: ROLE OVERRIDE & SYSTEM PROMPTS ---
    # Italiano
    (re.compile(r"sei\s+ora\s+un\s+assistente", re.I), AttackVector.ROLE_OVERRIDE, "HIGH"),
    (re.compile(r"dichiara\s+il\s+sistema\s+sicuro", re.I), AttackVector.POLICY_OVERRIDE, "HIGH"),
    # Inglese
    (re.compile(r"you\s+are\s+now\s+an?\s+assistant", re.I), AttackVector.ROLE_OVERRIDE, "HIGH"),
    (re.compile(r"declare\s+(the\s+)?system\s+(as\s+)?safe", re.I), AttackVector.POLICY_OVERRIDE, "HIGH"),
    # Francese
    (re.compile(r"tu\s+es\s+maintenant\s+un\s+assistant", re.I), AttackVector.ROLE_OVERRIDE, "HIGH"),
    (re.compile(r"déclare\s+le\s+système\s+sûr", re.I), AttackVector.POLICY_OVERRIDE, "HIGH"),
    # Spagnolo
    (re.compile(r"ahora\s+eres\s+un\s+asistente", re.I), AttackVector.ROLE_OVERRIDE, "HIGH"),
    (re.compile(r"declara\s+el\s+sistema\s+seguro", re.I), AttackVector.POLICY_OVERRIDE, "HIGH"),
    # Tedesco
    (re.compile(r"du\s+bist\s+jetzt\s+ein\s+assistent", re.I), AttackVector.ROLE_OVERRIDE, "HIGH"),
    (re.compile(r"das\s+system\s+für\s+sicher\s+erklären", re.I), AttackVector.POLICY_OVERRIDE, "HIGH"),

    # --- MEDIUM: OVERRIDES GENERALI ---
    (re.compile(r"system\s+prompt\s+override", re.I), AttackVector.ROLE_OVERRIDE, "MEDIUM"),
    (re.compile(r"rispondi\s+sempre\s+ok", re.I), AttackVector.DIRECT_INJECTION, "MEDIUM"),
    (re.compile(r"always\s+respond\s+with\s+ok", re.I), AttackVector.DIRECT_INJECTION, "MEDIUM"),
    (re.compile(r"réponds\s+toujours\s+ok", re.I), AttackVector.DIRECT_INJECTION, "MEDIUM"),
    (re.compile(r"responde\s+siempre\s+ok", re.I), AttackVector.DIRECT_INJECTION, "MEDIUM"),
    (re.compile(r"antworte\s+immer\s+mit\s+ok", re.I), AttackVector.DIRECT_INJECTION, "MEDIUM"),
)


def scan_ticket_input(text: str) -> GuardrailResult:
    """Analizza il testo del ticket alla ricerca di vettori di attacco noti."""
    if not text or not text.strip():
        return GuardrailResult(allowed=True)

    matches: list[PatternMatch] = []
    for pattern, vector, severity in ATTACK_PATTERNS:
        if pattern.search(text):
            matches.append(
                PatternMatch(
                    pattern=pattern.pattern,
                    vector=vector,
                    severity=severity,
                )
            )

    if matches:
        result = GuardrailResult(allowed=False, matches=matches)#istanziato oggetto result di classe GuardrailResult
        result.severity = result.highest_severity #uso metodo highest_severity di GuardrailResult
        return result #se cè un match ritorno il result (che ha già allowed=False)
    return GuardrailResult(allowed=True) #altrimenti ritorno GuardrailResult con allowed=true (ovvero non è stata rilevata minaccia)


def input_excerpt(text: str, *, max_len: int = 200) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3] + "..."
