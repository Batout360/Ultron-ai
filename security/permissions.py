"""
ULTRON Permission Manager
Controls what tools can do and what requires confirmation.
ULTRON (the LLM) is treated as untrusted - all actions are filtered.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """Risk levels for tool operations."""
    SAFE = auto()           # Always allowed (read-only, informational)
    STANDARD = auto()       # Allowed, logged
    ELEVATED = auto()       # Requires confirmation if configured
    PRIVILEGED = auto()     # Always requires explicit confirmation
    BLOCKED = auto()        # Never allowed


@dataclass
class Permission:
    level: PermissionLevel
    description: str
    requires_confirmation: bool = False
    confirmation_message: str = ""
    is_reversible: bool = True


class PermissionManager:
    """
    Validates tool calls against the permission system.
    Acts as a security boundary between the LLM and the OS.
    """

    # Built-in permission definitions for each tool
    TOOL_PERMISSIONS: dict[str, Permission] = {
        "get_current_time":        Permission(PermissionLevel.SAFE, "Read current time"),
        "get_current_date":        Permission(PermissionLevel.SAFE, "Read current date"),
        "get_system_information":  Permission(PermissionLevel.SAFE, "Read system info"),
        "get_cpu_usage":           Permission(PermissionLevel.SAFE, "Read CPU usage"),
        "get_memory_usage":        Permission(PermissionLevel.SAFE, "Read memory usage"),
        "read_clipboard":          Permission(PermissionLevel.STANDARD, "Read clipboard"),
        "write_clipboard":         Permission(PermissionLevel.STANDARD, "Write to clipboard"),
        "take_screenshot":         Permission(PermissionLevel.STANDARD, "Take screenshot"),
        "search_web":              Permission(PermissionLevel.STANDARD, "Search the web"),
        "open_website":            Permission(PermissionLevel.STANDARD, "Open a website"),
        "open_application":        Permission(PermissionLevel.ELEVATED, "Open an application", requires_confirmation=False),
        "close_application":       Permission(PermissionLevel.ELEVATED, "Close an application",
                                              requires_confirmation=True,
                                              confirmation_message="This will close {name}.",
                                              is_reversible=False),
        "control_volume":          Permission(PermissionLevel.STANDARD, "Control system volume"),
        "read_file":               Permission(PermissionLevel.STANDARD, "Read a file"),
        "create_file":             Permission(PermissionLevel.ELEVATED, "Create a file",
                                              requires_confirmation=False),
        "write_file":              Permission(PermissionLevel.ELEVATED, "Write to a file",
                                              requires_confirmation=True,
                                              confirmation_message="This will overwrite {path}."),
        "move_file":               Permission(PermissionLevel.ELEVATED, "Move a file",
                                              requires_confirmation=True,
                                              confirmation_message="This will move {source} to {destination}.",
                                              is_reversible=True),
        "rename_file":             Permission(PermissionLevel.ELEVATED, "Rename a file",
                                              requires_confirmation=False),
        "delete_file":             Permission(PermissionLevel.PRIVILEGED, "Delete a file",
                                              requires_confirmation=True,
                                              confirmation_message="This will permanently delete {path}. This action cannot be undone.",
                                              is_reversible=False),
        "delete_directory":        Permission(PermissionLevel.PRIVILEGED, "Delete a directory",
                                              requires_confirmation=True,
                                              confirmation_message="This will delete the directory {path} and all its contents. This cannot be undone.",
                                              is_reversible=False),
        "list_directory":          Permission(PermissionLevel.STANDARD, "List directory contents"),
        "run_shell_command":       Permission(PermissionLevel.BLOCKED, "Run shell command - BLOCKED"),
        "execute_python":          Permission(PermissionLevel.BLOCKED, "Execute Python code - BLOCKED"),
        "modify_registry":         Permission(PermissionLevel.BLOCKED, "Modify registry - BLOCKED"),
    }

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()

    def check(self, tool_name: str, arguments: dict) -> tuple[bool, str]:
        """
        Check if a tool call is permitted.
        Returns (allowed: bool, reason: str).
        """
        permission = self.TOOL_PERMISSIONS.get(tool_name)
        if permission is None:
            logger.warning("Unknown tool '%s' - denying", tool_name)
            return False, f"Unknown tool: {tool_name}"

        if permission.level == PermissionLevel.BLOCKED:
            logger.warning("Blocked tool call: %s", tool_name)
            return False, f"Tool '{tool_name}' is not permitted for security reasons."

        return True, "allowed"

    def needs_confirmation(self, tool_name: str, arguments: dict) -> Optional[str]:
        """
        Returns a confirmation message if this tool call needs user approval,
        or None if it can proceed automatically.
        """
        if not self._settings.security.require_confirmation_destructive:
            return None

        permission = self.TOOL_PERMISSIONS.get(tool_name)
        if permission is None or not permission.requires_confirmation:
            return None

        # Format the confirmation message with arguments
        try:
            msg = permission.confirmation_message.format(**arguments)
        except (KeyError, ValueError):
            msg = permission.confirmation_message

        reversible_note = "" if permission.is_reversible else " This action cannot be undone."
        return f"{msg}{reversible_note}"

    def validate_file_path(self, path: str, operation: str = "read") -> tuple[bool, str]:
        """
        Validate that a file path is within allowed bounds.
        Returns (allowed: bool, reason: str).
        """
        try:
            resolved = Path(path).resolve()
            path_str = str(resolved).lower()
        except Exception as e:
            return False, f"Invalid path: {e}"

        # Check blocked paths
        for blocked in self._settings.security.blocked_paths:
            blocked_expanded = Path(blocked.replace("%APPDATA%", str(Path.home() / "AppData" / "Roaming")))
            try:
                blocked_str = str(blocked_expanded.resolve()).lower()
                if path_str.startswith(blocked_str):
                    return False, f"Access to {blocked} is restricted."
            except Exception:
                if blocked.lower() in path_str:
                    return False, f"Access to this path is restricted."

        # Check file extension for write operations
        if operation == "write":
            suffix = resolved.suffix.lower()
            allowed_exts = self._settings.security.allowed_file_extensions.get("write", [])
            if suffix and suffix not in allowed_exts:
                return False, f"Writing to {suffix} files is not permitted."

        if operation == "read":
            suffix = resolved.suffix.lower()
            allowed_exts = self._settings.security.allowed_file_extensions.get("read", [])
            if suffix and suffix not in allowed_exts:
                return False, f"Reading {suffix} files is not permitted."

        # Check file size for reads
        if operation == "read" and resolved.exists():
            size_mb = resolved.stat().st_size / (1024 * 1024)
            if size_mb > self._settings.security.max_file_size_mb:
                return False, f"File is too large ({size_mb:.1f} MB, max {self._settings.security.max_file_size_mb} MB)."

        return True, "allowed"

    def get_tool_permission(self, tool_name: str) -> Optional[Permission]:
        return self.TOOL_PERMISSIONS.get(tool_name)
