"""
ULTRON Tool Registry
Central registry for all tools available to the LLM.
Tools are validated against the permission system before execution.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from config.settings import Settings, get_settings
from core.event_bus import EventBus, Event, EventType, get_event_bus
from security.permissions import PermissionManager
from security.confirmations import ConfirmationManager

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Schema for a tool callable by the LLM."""
    name: str
    description: str
    parameters: dict            # JSON Schema for parameters
    handler: Callable
    requires_confirmation: bool = False

    def to_ollama_format(self) -> dict:
        """Convert to Ollama tool definition format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """
    Registry of all tools available to ULTRON.
    Handles permission checking, confirmation, and execution.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        bus: Optional[EventBus] = None,
        permissions: Optional[PermissionManager] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._bus = bus or get_event_bus()
        self._permissions = permissions or PermissionManager(settings)
        self._confirmations = ConfirmationManager(bus=self._bus)
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def register_all(self) -> None:
        """Register all built-in tools."""
        from tools.system import get_system_tools
        from tools.browser import get_browser_tools
        from tools.files import get_file_tools
        from tools.applications import get_application_tools

        for tool in get_system_tools():
            self.register(tool)
        for tool in get_browser_tools():
            self.register(tool)
        for tool in get_file_tools(self._settings):
            self.register(tool)
        for tool in get_application_tools():
            self.register(tool)

        logger.info("Registered %d tools", len(self._tools))

    async def execute(self, tool_name: str, arguments: dict) -> Any:
        """
        Execute a tool by name with given arguments.
        Runs permission check and confirmation before calling the handler.
        """
        # 1. Lookup
        tool = self._tools.get(tool_name)
        if tool is None:
            raise ValueError(f"Unknown tool: {tool_name}")

        # 2. Permission check
        allowed, reason = self._permissions.check(tool_name, arguments)
        if not allowed:
            raise PermissionError(f"Tool '{tool_name}' is not allowed: {reason}")

        # 3. Confirmation if needed
        confirm_msg = self._permissions.needs_confirmation(tool_name, arguments)
        if confirm_msg:
            approved = await self._confirmations.request_confirmation(
                tool_name=tool_name,
                tool_arguments=arguments,
                message=confirm_msg,
            )
            if not approved:
                return f"Action '{tool_name}' was cancelled by the user."

        # 4. Execute
        await self._bus.publish(Event(
            type=EventType.TOOL_CALL_STARTED,
            data={"tool": tool_name, "arguments": arguments},
        ))

        try:
            result = tool.handler(**arguments)
            if asyncio.iscoroutine(result):
                result = await result

            await self._bus.publish(Event(
                type=EventType.TOOL_CALL_RESULT,
                data={"tool": tool_name, "result": str(result)[:500]},
            ))
            return result

        except TypeError as e:
            raise ValueError(f"Invalid arguments for tool '{tool_name}': {e}")
        except Exception as e:
            logger.error("Tool '%s' failed: %s", tool_name, e, exc_info=True)
            await self._bus.publish(Event(
                type=EventType.TOOL_CALL_ERROR,
                data={"tool": tool_name, "error": str(e)},
                error=e,
            ))
            raise

    def get_tool_definitions(self) -> list[dict]:
        """Return all tool definitions in Ollama/OpenAI format."""
        return [t.to_ollama_format() for t in self._tools.values()]

    def get_tool_names(self) -> list[str]:
        return list(self._tools.keys())

    @property
    def tool_count(self) -> int:
        return len(self._tools)
