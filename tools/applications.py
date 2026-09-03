"""
ULTRON Application Tools
Open, close, and interact with Windows applications.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Optional

from tools.registry import ToolDefinition

logger = logging.getLogger(__name__)


# Safe application whitelist - prevents arbitrary execution
ALLOWED_APPLICATIONS: dict[str, str] = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "notepad": "notepad.exe",
    "notepad++": "notepad++.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "paint": "mspaint.exe",
    "task manager": "taskmgr.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "vscode": "code.exe",
    "visual studio code": "code.exe",
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
    "spotify": "Spotify.exe",
    "vlc": "vlc.exe",
    "discord": "Discord.exe",
    "slack": "slack.exe",
    "steam": "steam.exe",
    "obs": "obs64.exe",
}


def open_application(name: str, arguments: str = "") -> str:
    """
    Open an application by name.
    Only applications in the allowed list can be opened.
    """
    name_lower = name.lower().strip()
    executable = ALLOWED_APPLICATIONS.get(name_lower)

    if not executable:
        # Check if it's a close match
        matches = [k for k in ALLOWED_APPLICATIONS if name_lower in k or k in name_lower]
        if matches:
            return f"Did you mean: {', '.join(matches)}? I can open any of those."
        return (
            f"'{name}' is not in my allowed application list. "
            f"I can open: {', '.join(sorted(ALLOWED_APPLICATIONS.keys())[:10])}..."
        )

    try:
        if arguments:
            subprocess.Popen([executable] + arguments.split(), shell=True)
        else:
            os.startfile(executable) if sys.platform == "win32" else subprocess.Popen([executable])
        return f"Opening {name}."
    except FileNotFoundError:
        # Try with startfile for Windows app shortcuts
        try:
            subprocess.Popen(executable, shell=True)
            return f"Opening {name}."
        except Exception as e:
            return f"Could not open {name}: Application not found. Make sure it's installed."
    except Exception as e:
        return f"Failed to open {name}: {e}"


def close_application(name: str) -> str:
    """
    Close an application by process name.
    Requires confirmation (handled by permission system).
    """
    name_lower = name.lower().strip()
    executable = ALLOWED_APPLICATIONS.get(name_lower, name)

    # Get just the exe name
    exe_name = os.path.basename(executable)

    try:
        result = subprocess.run(
            ["taskkill", "/IM", exe_name, "/F"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return f"Closed {name}."
        else:
            return f"Could not close {name}: {result.stderr.strip() or 'Process not found'}"
    except Exception as e:
        return f"Failed to close {name}: {e}"


def list_running_applications() -> str:
    """List currently running applications (not background processes)."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | Select-Object -Property Name,MainWindowTitle | Sort-Object Name | Format-Table -AutoSize"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                return f"Running applications:\n{output}"
            return "No visible applications currently running."
        return f"Could not list applications: {result.stderr}"
    except Exception as e:
        return f"Error listing applications: {e}"


def get_application_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="open_application",
            description="Open an application by name (e.g., 'Chrome', 'Notepad', 'Calculator')",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Application name (e.g., 'Chrome', 'Notepad', 'Calculator', 'VS Code')",
                    },
                    "arguments": {
                        "type": "string",
                        "description": "Optional command-line arguments",
                    },
                },
                "required": ["name"],
            },
            handler=open_application,
        ),
        ToolDefinition(
            name="close_application",
            description="Close a running application by name",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Application name to close",
                    },
                },
                "required": ["name"],
            },
            handler=close_application,
            requires_confirmation=True,
        ),
        ToolDefinition(
            name="list_running_applications",
            description="List all currently running applications with visible windows",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=list_running_applications,
        ),
    ]
