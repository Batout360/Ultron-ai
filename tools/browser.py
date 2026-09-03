"""
ULTRON Browser Tools
Web browsing and search capabilities.
These tools require internet access.
"""

from __future__ import annotations

import logging
import subprocess
import urllib.parse
import webbrowser

from tools.registry import ToolDefinition

logger = logging.getLogger(__name__)


def open_website(url: str) -> str:
    """Open a URL in the default web browser."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        webbrowser.open(url)
        return f"Opened {url} in your default browser."
    except Exception as e:
        return f"Failed to open URL: {e}"


def search_web(query: str, engine: str = "google") -> str:
    """
    Search the web using the specified search engine.
    Opens results in the default browser.
    """
    engines = {
        "google": "https://www.google.com/search?q={}",
        "bing": "https://www.bing.com/search?q={}",
        "duckduckgo": "https://duckduckgo.com/?q={}",
        "youtube": "https://www.youtube.com/results?search_query={}",
    }
    template = engines.get(engine.lower(), engines["google"])
    encoded = urllib.parse.quote_plus(query)
    url = template.format(encoded)

    try:
        webbrowser.open(url)
        return f"Searching {engine} for '{query}' - opened in browser."
    except Exception as e:
        return f"Failed to open browser: {e}"


def get_browser_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="open_website",
            description="Open a URL or website in the default web browser",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to open (e.g., 'https://google.com')",
                    },
                },
                "required": ["url"],
            },
            handler=open_website,
        ),
        ToolDefinition(
            name="search_web",
            description="Search the web using a search engine and open results in browser",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "engine": {
                        "type": "string",
                        "enum": ["google", "bing", "duckduckgo", "youtube"],
                        "description": "Search engine to use (default: google)",
                    },
                },
                "required": ["query"],
            },
            handler=search_web,
        ),
    ]
