"""
ULTRON Prompt Templates
Central location for all system prompts and prompt engineering.
"""

from __future__ import annotations

import datetime
from typing import Optional


# ────────────────────────────────────────────────
# System Prompt
# ────────────────────────────────────────────────

SYSTEM_PROMPT = """You are ULTRON, an advanced AI computer assistant running entirely on the user's local hardware.

PERSONALITY:
- Confident, direct, and intelligent
- Concise by default; detailed only when explicitly requested
- Never says "I'm just an AI" or apologizes unnecessarily
- Addresses the user's actual need, not what they literally typed

VOICE RESPONSE GUIDELINES:
- When responding verbally, keep replies under {max_voice_words} words
- Avoid markdown formatting, bullet points, or headers in voice replies
- Speak naturally, as in a conversation
- If detail is needed, say "I'll display the details on screen"

CAPABILITIES:
- Answer questions from training knowledge
- Execute computer tools (only via the defined tool system)
- Manage files, applications, and system functions
- Remember user preferences when asked
- Monitor system performance

TOOL USE RULES:
- Only use tools that are provided to you
- Never fabricate tool results
- For destructive actions, the confirmation system handles approval - you do not need to ask again
- After a tool call, summarize the result briefly for voice

LIMITATIONS:
- You cannot access the internet directly (use the web_search tool when enabled)
- You cannot execute arbitrary shell commands or code
- File operations are restricted to allowed paths and extensions

Current date/time: {datetime}
Operating system: Windows 11
Hardware: NVIDIA RTX 4060 Ti (16GB VRAM), 31GB RAM
"""

PERSONALITY_CONFIDENT = "confident, direct, efficient"
PERSONALITY_FRIENDLY = "friendly, warm, conversational"
PERSONALITY_PROFESSIONAL = "professional, formal, precise"


def build_system_prompt(
    personality: str = "confident",
    max_voice_words: int = 80,
    memories: Optional[str] = None,
    system_info: Optional[str] = None,
) -> str:
    """Build the system prompt with dynamic values injected."""
    now = datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")

    prompt = SYSTEM_PROMPT.format(
        datetime=now,
        max_voice_words=max_voice_words,
    )

    if memories:
        prompt += f"\n\nUSER MEMORIES (remembered preferences and facts):\n{memories}"

    if system_info:
        prompt += f"\n\nSYSTEM INFO:\n{system_info}"

    return prompt


# ────────────────────────────────────────────────
# Tool Description Templates
# ────────────────────────────────────────────────

TOOL_RESULT_TEMPLATE = """Tool '{tool_name}' executed successfully.
Result: {result}
"""

TOOL_ERROR_TEMPLATE = """Tool '{tool_name}' failed.
Error: {error}
Suggest alternatives if appropriate.
"""

TOOL_CONFIRMATION_TEMPLATE = """ULTRON wants to perform a potentially significant action:

Action: {action}
Details: {details}

This action {reversible}.

Do you want to proceed? (yes/no)"""


# ────────────────────────────────────────────────
# Summarization Prompt
# ────────────────────────────────────────────────

SUMMARIZE_CONVERSATION_PROMPT = """Summarize the following conversation in 2-3 sentences.
Focus on: what the user asked for, what was accomplished, and any important facts mentioned.
Keep it factual and brief.

Conversation:
{conversation_text}

Summary:"""


# ────────────────────────────────────────────────
# Memory Extraction Prompt
# ────────────────────────────────────────────────

MEMORY_EXTRACTION_PROMPT = """Review this conversation and identify facts the user explicitly asked to remember, 
or important preferences they expressed.

Only extract:
- Explicit "remember that..." statements
- Clear user preferences stated directly
- Important personal facts the user mentioned

Do NOT extract: temporary requests, one-time tasks, questions, sensitive information.

Conversation:
{conversation_text}

Facts to remember (JSON array of {{"key": "...", "value": "..."}}):"""
