"""Tool layer STEP 3 — funzioni Python invocabili dall'Agente 2 via OpenAI tool calling."""

from src.tools.tools import (
    OPENAI_TOOLS,
    TOOL_MAP,
    execute_tool,
    get_order_status,
    get_support_policy,
    issue_refund,
)

__all__ = [
    "OPENAI_TOOLS",
    "TOOL_MAP",
    "execute_tool",
    "get_order_status",
    "get_support_policy",
    "issue_refund",
]

"""Se controlli, non troverai nessun file in tutto il progetto che importa le funzioni
dei tools dal file tools.py. Questo perchè questa pagina __init__ fa da interfaccia-facade.
__all__ stabilisce quali metodi possono essere riachiamati-esposti solamente facendo l'import
 all'altezza della cartella tools: from src.tools import OPENAI_TOOLS, execute_tool

 in altre parole: all'interno del file __init__ posso fare tutti gli import da tutti i file
 di tutto il progetto che mi servono:

from src.tools.tools import (
    OPENAI_TOOLS,
    TOOL_MAP,
    .....
)
from src.models... import....
from logs.... import....(ma è prassi mantenersi all'interno della propria sottocartella...)

e poi di questi file inserisco le funzioni che voglio esporre in __all__

In pratica è come se avessi fatto diventare la cartella tools una libreria-package-servizio
che espone le sue operations...

"""