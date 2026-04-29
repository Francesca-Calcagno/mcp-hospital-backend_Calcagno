"""Moduli di supporto per la gestione dei tool e delle risposte del modello."""

from __future__ import annotations

from typing import Any


def mcp_tools_to_anthropic(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    """Converte i tool MCP nel formato richiesto dall’API Anthropic."""
    return [
        {
            "name": t.name,
            "description": t.description or "",
            "input_schema": t.inputSchema,
        }
        for t in mcp_tools
    ]


def mcp_result_to_text(result: Any) -> tuple[str, bool]:
    """Estrae testo da un risultato MCP e segnala se ci sono errori."""
    parts: list[str] = []
    for block in result.content:
        text = getattr(block, "text", None)
        parts.append(text if text is not None else str(block))
    return "\n".join(parts), bool(getattr(result, "isError", False))
