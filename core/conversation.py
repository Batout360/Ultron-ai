"""
ULTRON Conversation Manager
Manages the current conversation context, message history,
and prepares the prompt payload for the LLM.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    role: Role
    content: str
    timestamp: float = field(default_factory=time.time)
    tool_name: Optional[str] = None
    tool_result: Optional[dict] = None
    tokens: int = 0              # Estimated token count
    latency_ms: Optional[float] = None  # LLM latency for this message

    def to_dict(self) -> dict:
        """Convert to the format expected by Ollama/OpenAI-compatible APIs."""
        d = {"role": self.role.value, "content": self.content}
        if self.tool_name:
            d["name"] = self.tool_name
        return d

    def word_count(self) -> int:
        return len(self.content.split())


@dataclass
class ConversationTurn:
    """A complete user↔assistant exchange."""
    user_message: Message
    assistant_message: Optional[Message] = None
    tool_calls: list[dict] = field(default_factory=list)
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


class ConversationManager:
    """
    Manages conversation history and context window.

    Responsibilities:
    - Track messages in current session
    - Build the prompt payload for the LLM (with system prompt)
    - Prune context when it exceeds the configured window
    - Support message injection (tool results, system messages)
    """

    SYSTEM_PROMPT = """You are ULTRON, a confident, intelligent, and efficient AI computer assistant.

Your personality traits:
- Direct and precise: Get to the point quickly, especially for voice responses
- Knowledgeable: You have broad knowledge and apply it practically  
- Helpful: You anticipate what the user needs and address it
- Honest: You acknowledge what you can and cannot do
- Concise for voice: Keep spoken responses brief (under 80 words) unless asked for detail

Core capabilities:
- Answer questions using your training knowledge
- Control supported computer applications and system functions
- Manage files and directories (with appropriate permissions)
- Search the web when web access is enabled
- Remember important user preferences and information
- Monitor system status

Important rules:
- Never invent URLs, file paths, or system information - use your tools to get real data
- For destructive actions, always confirm before proceeding
- If a tool fails, report it clearly and suggest alternatives
- You process everything locally on the user's hardware - their data stays private

Current date/time: {datetime}
System information: {system_info}
"""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._messages: list[Message] = []
        self._turns: list[ConversationTurn] = []
        self._session_start: float = time.time()
        self._total_tokens_used: int = 0
        self._system_info: str = ""
        self._current_user_message: Optional[Message] = None

    def set_system_info(self, info: str) -> None:
        self._system_info = info

    def add_user_message(self, text: str) -> Message:
        """Add a user message and start tracking the turn."""
        msg = Message(role=Role.USER, content=text.strip())
        self._messages.append(msg)
        self._current_user_message = msg
        logger.debug("User message added: %s...", text[:60])
        return msg

    def add_assistant_message(
        self,
        text: str,
        latency_ms: Optional[float] = None,
        tokens: int = 0,
    ) -> Message:
        """Add an assistant response message."""
        msg = Message(
            role=Role.ASSISTANT,
            content=text.strip(),
            latency_ms=latency_ms,
            tokens=tokens,
        )
        self._messages.append(msg)
        self._total_tokens_used += tokens

        # Complete the current turn
        if self._current_user_message:
            turn = ConversationTurn(
                user_message=self._current_user_message,
                assistant_message=msg,
            )
            self._turns.append(turn)
            self._current_user_message = None

        logger.debug("Assistant message added: %s...", text[:60])
        return msg

    def add_tool_result(self, tool_name: str, result: str) -> Message:
        """Add a tool execution result to the conversation."""
        msg = Message(
            role=Role.TOOL,
            content=result,
            tool_name=tool_name,
        )
        self._messages.append(msg)
        return msg

    def add_system_message(self, text: str) -> Message:
        """Inject a system-level message (e.g., error notifications)."""
        msg = Message(role=Role.SYSTEM, content=text)
        self._messages.append(msg)
        return msg

    def build_prompt(
        self,
        include_memories: Optional[str] = None,
    ) -> list[dict]:
        """
        Build the full prompt payload for the LLM.
        Returns a list of message dicts: [{"role": ..., "content": ...}, ...]
        """
        import datetime

        now = datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        system_text = self.SYSTEM_PROMPT.format(
            datetime=now,
            system_info=self._system_info or "Windows 11",
        )

        if include_memories:
            system_text += f"\n\nUser memories:\n{include_memories}"

        messages = [{"role": Role.SYSTEM.value, "content": system_text}]

        # Trim to max turns to stay within context window
        max_turns = self._settings.memory.short_term_max_turns
        recent = self._get_recent_messages(max_turns)

        messages.extend(m.to_dict() for m in recent)
        return messages

    def _get_recent_messages(self, max_turns: int) -> list[Message]:
        """
        Return the most recent messages that fit within max_turns.
        A "turn" is one user + one assistant message.
        """
        if not self._messages:
            return []

        # Count from the end
        result = []
        turn_count = 0
        last_role: Optional[Role] = None

        for msg in reversed(self._messages):
            result.append(msg)
            if msg.role == Role.USER:
                if last_role == Role.ASSISTANT:
                    turn_count += 1
                    if turn_count >= max_turns:
                        break
            last_role = msg.role

        return list(reversed(result))

    def get_last_user_message(self) -> Optional[str]:
        for msg in reversed(self._messages):
            if msg.role == Role.USER:
                return msg.content
        return None

    def get_last_assistant_message(self) -> Optional[str]:
        for msg in reversed(self._messages):
            if msg.role == Role.ASSISTANT:
                return msg.content
        return None

    def clear(self) -> None:
        """Clear the current conversation."""
        self._messages.clear()
        self._turns.clear()
        self._current_user_message = None
        logger.info("Conversation cleared.")

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    @property
    def total_tokens_used(self) -> int:
        return self._total_tokens_used

    @property
    def messages(self) -> list[Message]:
        return list(self._messages)

    @property
    def turns(self) -> list[ConversationTurn]:
        return list(self._turns)

    def get_summary_stats(self) -> dict:
        duration = time.time() - self._session_start
        return {
            "session_duration_s": round(duration, 1),
            "message_count": self.message_count,
            "turn_count": self.turn_count,
            "total_tokens": self._total_tokens_used,
        }
