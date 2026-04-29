"""Valutazione qualitativa delle risposte del backend.

Contiene logiche di stima della confidenza e di controllo qualità in modo
che la risposta finale riporti un valore numerico e note di valutazione.
"""

from __future__ import annotations

from typing import Any


def compute_confidence(
    answer: str,
    tool_calls: list[dict[str, Any]],
    iterations: int,
    has_tool_errors: bool,
) -> float:
    """Ritorna una stima semplice di confidenza basata sulla qualità del flusso."""
    confidence = 0.75

    if has_tool_errors:
        confidence -= 0.30
    if not tool_calls:
        confidence -= 0.15

    if iterations >= 4:
        confidence += 0.05
    if iterations >= 7:
        confidence -= 0.10

    lowered = answer.lower()
    if "non posso" in lowered or "non so" in lowered or "non disponibile" in lowered:
        confidence = min(confidence, 0.65)

    if confidence < 0:
        return 0.0
    if confidence > 1:
        return 1.0
    return round(confidence, 2)


def build_quality_checks(
    answer: str,
    tool_calls: list[dict[str, Any]],
    iterations: int,
    has_tool_errors: bool,
) -> list[str]:
    """Genera una lista di note sulla qualità della risposta."""
    notes: list[str] = []

    if not tool_calls:
        notes.append("Nessun tool è stato utilizzato per questa risposta.")

    if has_tool_errors:
        notes.append("Almeno un tool ha restituito un errore o una risposta invalida.")

    if iterations >= 5:
        notes.append(
            "Il modello ha richiesto molte iterazioni; potrebbe esserci incertezza nella decisione sui tool o nei dati.",
        )
    elif iterations == 1 and tool_calls:
        notes.append("Risposta prodotta rapidamente con un singolo ciclo di tool.")

    if "non posso" in answer.lower() or "non so" in answer.lower():
        notes.append("Il modello ha espresso incertezza nel contenuto della risposta.")

    if not notes:
        notes.append("Nessuna anomalia di qualità rilevata. Risposta coerente con i dati disponibili.")

    return notes
