"""Client MCP stdio: spawna `server.py` come subprocess e mantiene la sessione viva."""

from __future__ import annotations

import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

SERVER_PATH = Path(__file__).resolve().parent.parent / "server.py"


class MCPClient:
    def __init__(self, server_path: Path = SERVER_PATH) -> None:
        self.server_path = server_path
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._tools: list[Any] = []

    async def connect(self) -> None:
        stack = AsyncExitStack()
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(self.server_path)],
        )
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._tools = (await session.list_tools()).tools
        self._stack = stack
        self._session = session

    async def disconnect(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self._session = None

    @property
    def tools(self) -> list[Any]:
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        if self._session is None:
            raise RuntimeError("MCP client not connected")
        return await self._session.call_tool(name, arguments)
