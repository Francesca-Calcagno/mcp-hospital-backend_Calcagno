"""Pipeline a 6 step: input → parsing LLM → validazione → normalizzazione → tool exec → output."""

from __future__ import annotations

from typing import Any

import anthropic

from .agent import mcp_result_to_text, mcp_tools_to_anthropic
from .evaluator import build_quality_checks, compute_confidence
from .mcp_client import MCPClient
from .normalizer import normalize_arguments

MODEL = "claude-haiku"
MAX_ITERATIONS = 10
MAX_TOKENS = 4096

SYSTEM_PROMPT = """Sei un assistente clinico per il sistema ospedaliero SISCA.
Aiuti i medici a recuperare e aggiornare informazioni sui pazienti usando gli strumenti disponibili.

Regole:
- Rispondi sempre in italiano, in modo conciso e professionale.
- Usa gli strumenti per accedere a dati reali — non inventare mai informazioni cliniche.
- Quando il medico chiede di un paziente per nome, prima usa `search_patients_by_name` per trovare l'ID, poi gli altri tool.
- I codici dei reparti sono in inglese: cardiology, neurology, oncology, pediatrics, emergency.
- Per aggiornamenti (vitali, note, dimissioni) procedi se il medico è esplicito.
- Riporta i dati che il medico chiede senza preamboli inutili tipo "Ecco le informazioni richieste:"."""


def mcp_tools_to_anthropic(mcp_tools: list[Any]) -> list[dict]:
    """Converte i tool MCP nel formato Anthropic (lo schema JSON è già compatibile)."""
    return [
        {
            "name": t.name,
            "description": t.description or "",
            "input_schema": t.inputSchema,
        }
        for t in mcp_tools
    ]


def mcp_result_to_text(result: Any) -> tuple[str, bool]:
    parts: list[str] = []
    for block in result.content:
        text = getattr(block, "text", None)
        parts.append(text if text is not None else str(block))
    return "\n".join(parts), bool(getattr(result, "isError", False))


async def run_query(
    client: anthropic.AsyncAnthropic,
    mcp: MCPClient,
    question: str,
) -> tuple[str, list[dict], int, str, float, list[str]]:
    """
    Esegue il loop agentico: il modello sceglie i tool MCP da invocare finché non
    produce una risposta finale (`stop_reason == "end_turn"`).

    Returns: (answer, tool_calls_log, iterations, model_id, confidence, quality_checks)
    """
    tools = mcp_tools_to_anthropic(mcp.tools)
    tool_names = {t["name"] for t in tools}

    messages: list[dict] = [{"role": "user", "content": question}]
    tool_calls_log: list[dict] = []
    last_model = MODEL

    for iteration in range(1, MAX_ITERATIONS + 1):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=tools,
            messages=messages,
        )
        last_model = response.model

        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content if b.type == "text")
            has_tool_errors = any(call.get("error") for call in tool_calls_log)
            confidence = compute_confidence(text or "(nessuna risposta dal modello)", tool_calls_log, iteration, has_tool_errors)
            quality_checks = build_quality_checks(text or "(nessuna risposta dal modello)", tool_calls_log, iteration, has_tool_errors)
            return (
                text or "(nessuna risposta dal modello)",
                tool_calls_log,
                iteration,
                last_model,
                confidence,
                quality_checks,
            )

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            log_entry: dict[str, Any] = {"name": block.name, "arguments": dict(block.input)}

            if block.name not in tool_names:
                err = f"Tool '{block.name}' non disponibile"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": err,
                    "is_error": True,
                })
                log_entry["error"] = err
                tool_calls_log.append(log_entry)
                continue

            normalized = normalize_arguments(block.name, block.input)
            log_entry["arguments"] = normalized

            try:
                mcp_result = await mcp.call_tool(block.name, normalized)
                text, is_error = mcp_result_to_text(mcp_result)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": text,
                    "is_error": is_error,
                })
                log_entry["result"] = text[:1000]
                if is_error:
                    log_entry["error"] = "MCP returned isError=true"
            except Exception as e:
                err = f"Errore esecuzione tool: {e}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": err,
                    "is_error": True,
                })
                log_entry["error"] = str(e)

            tool_calls_log.append(log_entry)

        messages.append({"role": "user", "content": tool_results})

    raise RuntimeError(f"Max iterations ({MAX_ITERATIONS}) reached without final answer")
