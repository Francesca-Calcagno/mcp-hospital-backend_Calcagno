"""FastAPI app: espone /query, mantiene aperta la sessione MCP per la durata del processo."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .mcp_client import MCPClient
from .pipeline import run_query
from .schemas import QueryRequest, QueryResponse, ToolCall

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY env var is required")

    mcp = MCPClient()
    await mcp.connect()
    app.state.mcp = mcp
    app.state.anthropic = anthropic.AsyncAnthropic()
    try:
        yield
    finally:
        await mcp.disconnect()


app = FastAPI(
    title="SISCA Backend",
    description="Backend conversazionale per medici, integrato con MCP server SISCA.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    mcp: MCPClient = app.state.mcp
    return {
        "status": "ok",
        "mcp_tools": [t.name for t in mcp.tools],
        "tool_count": len(mcp.tools),
    }


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    try:
        answer, tool_calls, iterations, model = await run_query(
            app.state.anthropic,
            app.state.mcp,
            req.question,
        )
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return QueryResponse(
        answer=answer,
        tool_calls=[ToolCall(**tc) for tc in tool_calls],
        iterations=iterations,
        model=model,
    )
