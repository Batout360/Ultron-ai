# ui/web_ai_core.py — ULTRON 3.0
# WebEngine-based AI Core  — drop-in replacement for ui/ai_core.AICoreWidget
#
# Renders ui/brain_core.html (Three.js + WebGL particle swarm) inside a
# QWebEngineView that fills the centre panel.  Python pushes live AI state
# into the page via a single runJavaScript call every time update_ai_state()
# is called, which maps directly to the existing signal from AIEngine.
#
# Public API — identical to the QPainter AICoreWidget:
#   update_ai_state(data: dict)  — keys: neural, processing, confidence, task
#
# Requirements:
#   PySide6-WebEngine  (pip install PySide6-WebEngine)

from pathlib import Path

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore    import QWebEngineSettings
from PySide6.QtCore             import QUrl, Qt
from PySide6.QtWidgets          import QSizePolicy

# Absolute path to the HTML file sitting next to this module
_HTML_PATH = Path(__file__).parent / "brain_core.html"


class AICoreWidget(QWebEngineView):
    """
    Drop-in replacement for the QPainter AICoreWidget.

    Loads brain_core.html which runs the full 20 000-particle Three.js
    JARVIS Machine Brain at GPU quality.  AI state (neural%, proc%,
    conf%, task label) is forwarded into the page via JavaScript.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── Sizing ───────────────────────────────────────────────
        self.setMinimumSize(320, 320)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        # ── WebEngine settings ───────────────────────────────────
        settings = self.settings()
        # Allow local file access so the HTML can load Three.js from CDN
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            True,
        )
        # Enable WebGL (required for Three.js renderer)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.WebGLEnabled,
            True,
        )
        # Accelerated 2D canvas — helps overall compositing
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled,
            True,
        )
        # Disable the context menu (right-click) — keep the HUD clean
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,
            False,
        )

        # ── Load the HTML ────────────────────────────────────────
        self.load(QUrl.fromLocalFile(str(_HTML_PATH)))

        # ── Internal state (mirrors what the HTML shows) ─────────
        self._neural = 72.0
        self._proc   = 55.0
        self._conf   = 91.0
        self._task   = "MONITORING"

        # Push initial values once the page has loaded
        self.loadFinished.connect(self._on_load_finished)

    # ── Qt resize → tell the page ────────────────────────────────
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Nudge the page so ResizeObserver fires immediately (belt + suspenders)
        self.page().runJavaScript(
            "window.dispatchEvent(new Event('resize'));"
        )

    # ── Public API ────────────────────────────────────────────────
    def update_ai_state(self, data: dict):
        """
        Receive live AI state from AIEngine.state_updated signal.

        data keys (same as QPainter version):
            neural      float  0-100
            processing  float  0-100
            confidence  float  0-100
            task        str
        """
        self._neural = data.get("neural",     self._neural)
        self._proc   = data.get("processing", self._proc)
        self._conf   = data.get("confidence", self._conf)
        self._task   = data.get("task",       self._task)
        self._push_state()

    # ── Internal ──────────────────────────────────────────────────
    def _on_load_finished(self, ok: bool):
        """Called once the HTML + JS have loaded; push current state."""
        if ok:
            self._push_state()

    def _push_state(self):
        """
        Call window.updateAIState(neural, proc, conf, task) in the page.
        Uses proper JSON-safe escaping so task strings with special chars work.
        """
        import json
        task_json = json.dumps(str(self._task))   # e.g. '"MONITORING"'
        js = (
            f"if (typeof updateAIState === 'function') {{"
            f"  updateAIState("
            f"    {self._neural:.1f},"
            f"    {self._proc:.1f},"
            f"    {self._conf:.1f},"
            f"    {task_json}"
            f"  );"
            f"}}"
        )
        self.page().runJavaScript(js)
