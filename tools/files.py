"""
ULTRON File Tools
Safe file system operations with strict path validation.
All operations go through the permission system.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from config.settings import Settings, get_settings
from security.permissions import PermissionManager
from tools.registry import ToolDefinition

logger = logging.getLogger(__name__)


def _make_handlers(settings: Settings) -> dict:
    """Create closure handlers with settings injected for path validation."""
    permissions = PermissionManager(settings)

    def read_file(path: str) -> str:
        """Read and return the content of a text file."""
        allowed, reason = permissions.validate_file_path(path, "read")
        if not allowed:
            return f"Cannot read file: {reason}"
        try:
            p = Path(path).resolve()
            if not p.exists():
                return f"File not found: {path}"
            if not p.is_file():
                return f"Not a file: {path}"
            content = p.read_text(encoding="utf-8", errors="replace")
            if len(content) > 10000:
                content = content[:10000] + f"\n...[truncated, {len(content)} total chars]"
            return content
        except OSError as e:
            return f"Error reading file: {e}"

    def create_file(path: str, content: str = "") -> str:
        """Create a new file with optional content."""
        allowed, reason = permissions.validate_file_path(path, "write")
        if not allowed:
            return f"Cannot create file: {reason}"
        try:
            p = Path(path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"File created: {p}"
        except OSError as e:
            return f"Error creating file: {e}"

    def write_file(path: str, content: str) -> str:
        """Write content to an existing or new file (overwrites)."""
        allowed, reason = permissions.validate_file_path(path, "write")
        if not allowed:
            return f"Cannot write file: {reason}"
        try:
            p = Path(path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"File written: {p} ({len(content)} bytes)"
        except OSError as e:
            return f"Error writing file: {e}"

    def move_file(source: str, destination: str) -> str:
        """Move or rename a file."""
        allowed_src, reason = permissions.validate_file_path(source, "read")
        if not allowed_src:
            return f"Cannot access source: {reason}"
        allowed_dst, reason = permissions.validate_file_path(destination, "write")
        if not allowed_dst:
            return f"Cannot access destination: {reason}"
        try:
            src = Path(source).resolve()
            dst = Path(destination).resolve()
            if not src.exists():
                return f"Source not found: {source}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return f"Moved: {src} → {dst}"
        except OSError as e:
            return f"Error moving file: {e}"

    def rename_file(path: str, new_name: str) -> str:
        """Rename a file (keeping it in the same directory)."""
        allowed, reason = permissions.validate_file_path(path, "write")
        if not allowed:
            return f"Cannot rename: {reason}"
        try:
            p = Path(path).resolve()
            if not p.exists():
                return f"File not found: {path}"
            new_path = p.parent / new_name
            p.rename(new_path)
            return f"Renamed: {p.name} → {new_name}"
        except OSError as e:
            return f"Error renaming: {e}"

    def delete_file(path: str) -> str:
        """Delete a file (requires confirmation)."""
        allowed, reason = permissions.validate_file_path(path, "write")
        if not allowed:
            return f"Cannot delete: {reason}"
        try:
            p = Path(path).resolve()
            if not p.exists():
                return f"File not found: {path}"
            if p.is_dir():
                return f"Use delete_directory for directories."
            p.unlink()
            return f"Deleted: {p}"
        except OSError as e:
            return f"Error deleting: {e}"

    def list_directory(path: str = ".", pattern: str = "*") -> str:
        """List files and directories at a path."""
        try:
            p = Path(path).resolve()
            if not p.exists():
                return f"Directory not found: {path}"
            if not p.is_dir():
                return f"Not a directory: {path}"

            items = sorted(p.glob(pattern))
            if not items:
                return f"Directory is empty: {path}"

            lines = [f"Contents of {p}:", ""]
            dirs = [i for i in items if i.is_dir()]
            files = [i for i in items if i.is_file()]

            for d in dirs[:50]:
                lines.append(f"  [DIR]  {d.name}/")
            for f in files[:100]:
                size = f.stat().st_size
                size_str = f"{size:,} B" if size < 1024 else f"{size/1024:.1f} KB" if size < 1048576 else f"{size/1048576:.1f} MB"
                lines.append(f"  [FILE] {f.name} ({size_str})")

            if len(items) > 150:
                lines.append(f"\n  ... and {len(items) - 150} more items")

            return "\n".join(lines)
        except OSError as e:
            return f"Error listing directory: {e}"

    return {
        "read_file": read_file,
        "create_file": create_file,
        "write_file": write_file,
        "move_file": move_file,
        "rename_file": rename_file,
        "delete_file": delete_file,
        "list_directory": list_directory,
    }


def get_file_tools(settings: Optional[Settings] = None) -> list[ToolDefinition]:
    """Return all file tool definitions."""
    cfg = settings or get_settings()
    handlers = _make_handlers(cfg)

    return [
        ToolDefinition(
            name="read_file",
            description="Read and return the text content of a file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path"},
                },
                "required": ["path"],
            },
            handler=handlers["read_file"],
        ),
        ToolDefinition(
            name="create_file",
            description="Create a new file with optional content",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to create"},
                    "content": {"type": "string", "description": "Initial file content"},
                },
                "required": ["path"],
            },
            handler=handlers["create_file"],
        ),
        ToolDefinition(
            name="write_file",
            description="Write content to a file, overwriting if it exists",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
            handler=handlers["write_file"],
            requires_confirmation=True,
        ),
        ToolDefinition(
            name="move_file",
            description="Move or copy a file to a new location",
            parameters={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source file path"},
                    "destination": {"type": "string", "description": "Destination path"},
                },
                "required": ["source", "destination"],
            },
            handler=handlers["move_file"],
            requires_confirmation=True,
        ),
        ToolDefinition(
            name="rename_file",
            description="Rename a file (keeping it in the same directory)",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Current file path"},
                    "new_name": {"type": "string", "description": "New filename (without path)"},
                },
                "required": ["path", "new_name"],
            },
            handler=handlers["rename_file"],
        ),
        ToolDefinition(
            name="delete_file",
            description="Delete a file permanently",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to delete"},
                },
                "required": ["path"],
            },
            handler=handlers["delete_file"],
            requires_confirmation=True,
        ),
        ToolDefinition(
            name="list_directory",
            description="List the contents of a directory",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default: current directory)"},
                    "pattern": {"type": "string", "description": "Glob pattern (default: '*')"},
                },
                "required": [],
            },
            handler=handlers["list_directory"],
        ),
    ]
