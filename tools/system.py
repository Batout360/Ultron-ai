"""
ULTRON System Tools
Read-only system information and basic computer controls.
All system tools are in the SAFE or STANDARD permission level.
"""

from __future__ import annotations

import datetime
import logging
import platform
import subprocess
from typing import Any

from tools.registry import ToolDefinition

logger = logging.getLogger(__name__)


def get_current_time() -> str:
    """Get the current local time."""
    return datetime.datetime.now().strftime("%I:%M %p")


def get_current_date() -> str:
    """Get the current local date."""
    return datetime.datetime.now().strftime("%A, %B %d, %Y")


def get_system_information() -> dict[str, Any]:
    """Get detailed system information."""
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\')

        info = {
            "os": platform.system() + " " + platform.release(),
            "os_version": platform.version()[:50],
            "cpu": platform.processor()[:50],
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(logical=True),
            "cpu_usage_percent": round(cpu_percent, 1),
            "ram_total_gb": round(mem.total / (1024**3), 1),
            "ram_used_gb": round(mem.used / (1024**3), 1),
            "ram_free_gb": round(mem.available / (1024**3), 1),
            "ram_usage_percent": mem.percent,
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "disk_free_gb": round(disk.free / (1024**3), 1),
            "disk_usage_percent": round(disk.used / disk.total * 100, 1),
        }

        # GPU info
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                gpu_data = result.stdout.strip().split(",")
                if len(gpu_data) >= 4:
                    info["gpu"] = gpu_data[0].strip()
                    info["gpu_vram_total_mb"] = int(gpu_data[1].strip())
                    info["gpu_vram_used_mb"] = int(gpu_data[2].strip())
                    info["gpu_temp_c"] = int(gpu_data[3].strip())
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass

        return info
    except ImportError:
        return {"error": "psutil not installed", "os": platform.system()}


def get_cpu_usage() -> dict:
    """Get current CPU usage."""
    try:
        import psutil
        per_core = psutil.cpu_percent(interval=0.1, percpu=True)
        freq = psutil.cpu_freq()
        return {
            "total_percent": round(sum(per_core) / len(per_core), 1),
            "per_core": [round(c, 1) for c in per_core],
            "frequency_mhz": round(freq.current) if freq else None,
        }
    except ImportError:
        return {"error": "psutil not installed"}


def get_memory_usage() -> dict:
    """Get current memory usage."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024**3), 1),
            "used_gb": round(mem.used / (1024**3), 1),
            "available_gb": round(mem.available / (1024**3), 1),
            "percent": mem.percent,
        }
    except ImportError:
        return {"error": "psutil not installed"}


def take_screenshot(save_path: str = "") -> str:
    """Take a screenshot and save it to a file."""
    try:
        import PIL.ImageGrab as ImageGrab
        import time
        if not save_path:
            save_path = f"screenshot_{int(time.time())}.png"
        screenshot = ImageGrab.grab()
        screenshot.save(save_path)
        return f"Screenshot saved to: {save_path}"
    except ImportError:
        try:
            import subprocess
            import time
            if not save_path:
                save_path = f"screenshot_{int(time.time())}.png"
            # Use PowerShell as fallback
            ps_cmd = f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::PrimaryScreen | Out-Null; (New-Object -ComObject WScript.Shell).Run('', 0); [System.Drawing.Bitmap]::new([System.Windows.Forms.SystemInformation]::VirtualScreen.Width, [System.Windows.Forms.SystemInformation]::VirtualScreen.Height)"
            subprocess.run(["powershell", "-Command",
                f"Add-Type -AssemblyName System.Windows.Forms; "
                f"$bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height); "
                f"$g = [System.Drawing.Graphics]::FromImage($bmp); "
                f"$g.CopyFromScreen(0, 0, 0, 0, $bmp.Size); "
                f"$bmp.Save('{save_path}')"], check=True, timeout=10)
            return f"Screenshot saved to: {save_path}"
        except Exception as e:
            return f"Screenshot failed: {e}"


def read_clipboard() -> str:
    """Read the current clipboard content."""
    try:
        import pyperclip
        return pyperclip.paste() or "(clipboard is empty)"
    except ImportError:
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=3
            )
            return result.stdout.strip() or "(clipboard is empty)"
        except Exception as e:
            return f"Could not read clipboard: {e}"


def write_clipboard(text: str) -> str:
    """Write text to the clipboard."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return f"Copied to clipboard: {text[:100]}"
    except ImportError:
        try:
            subprocess.run(
                ["powershell", "-Command", f"Set-Clipboard -Value '{text}'"],
                timeout=3
            )
            return f"Copied to clipboard."
        except Exception as e:
            return f"Could not write to clipboard: {e}"


def control_volume(action: str, value: int = 10) -> str:
    """
    Control system volume.
    action: 'set', 'up', 'down', 'mute', 'unmute'
    value: percentage (0-100) for 'set', or step for up/down
    """
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        import math

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        if action == "set":
            vol = max(0.0, min(1.0, value / 100.0))
            volume.SetMasterVolumeLevelScalar(vol, None)
            return f"Volume set to {value}%"
        elif action == "up":
            current = volume.GetMasterVolumeLevelScalar()
            new_vol = min(1.0, current + value / 100.0)
            volume.SetMasterVolumeLevelScalar(new_vol, None)
            return f"Volume increased to {int(new_vol * 100)}%"
        elif action == "down":
            current = volume.GetMasterVolumeLevelScalar()
            new_vol = max(0.0, current - value / 100.0)
            volume.SetMasterVolumeLevelScalar(new_vol, None)
            return f"Volume decreased to {int(new_vol * 100)}%"
        elif action == "mute":
            volume.SetMute(1, None)
            return "Volume muted"
        elif action == "unmute":
            volume.SetMute(0, None)
            return "Volume unmuted"
        else:
            return f"Unknown action: {action}"
    except ImportError:
        # Fallback: nircmd or PowerShell
        try:
            if action == "mute":
                subprocess.run(["powershell", "-Command",
                    "(New-Object -com WScript.Shell).SendKeys([char]173)"], timeout=3)
                return "Volume muted"
            elif action == "set":
                ps = f"$vol = [int]({value} * 65535 / 100); (New-Object -com WScript.Shell).SendKeys([char]174)"
                return f"Volume adjusted"
        except Exception:
            pass
        return "Volume control requires pycaw: pip install pycaw"


def get_system_tools() -> list[ToolDefinition]:
    """Return all system tool definitions."""
    return [
        ToolDefinition(
            name="get_current_time",
            description="Get the current local time",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_current_time,
        ),
        ToolDefinition(
            name="get_current_date",
            description="Get the current local date",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_current_date,
        ),
        ToolDefinition(
            name="get_system_information",
            description="Get detailed system information including CPU, RAM, GPU usage, and disk space",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_system_information,
        ),
        ToolDefinition(
            name="get_cpu_usage",
            description="Get current CPU usage percentage",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_cpu_usage,
        ),
        ToolDefinition(
            name="get_memory_usage",
            description="Get current RAM usage",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_memory_usage,
        ),
        ToolDefinition(
            name="take_screenshot",
            description="Take a screenshot of the screen",
            parameters={
                "type": "object",
                "properties": {
                    "save_path": {
                        "type": "string",
                        "description": "Optional file path to save the screenshot. Defaults to a timestamped filename.",
                    },
                },
                "required": [],
            },
            handler=take_screenshot,
        ),
        ToolDefinition(
            name="read_clipboard",
            description="Read the current clipboard content",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=read_clipboard,
        ),
        ToolDefinition(
            name="write_clipboard",
            description="Write text to the clipboard",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to copy to clipboard"},
                },
                "required": ["text"],
            },
            handler=write_clipboard,
        ),
        ToolDefinition(
            name="control_volume",
            description="Control the system audio volume",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["set", "up", "down", "mute", "unmute"],
                        "description": "Volume action",
                    },
                    "value": {
                        "type": "integer",
                        "description": "Volume level (0-100) for 'set', or step size for 'up'/'down'",
                        "minimum": 0,
                        "maximum": 100,
                    },
                },
                "required": ["action"],
            },
            handler=control_volume,
        ),
    ]
