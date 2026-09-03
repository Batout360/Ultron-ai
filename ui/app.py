"""
ULTRON Qt Application
Integrates PyQt6 with asyncio using qasync.
This allows the Qt event loop and asyncio to run together.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def run_app(assistant=None, settings=None) -> int:
    """
    Start the Qt application with asyncio integration.
    Returns the exit code.
    """
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QFont, QPalette, QColor
        from PyQt6.QtCore import Qt
    except ImportError:
        logger.error("PyQt6 not installed: pip install PyQt6")
        print("ERROR: PyQt6 not installed. Run: pip install PyQt6")
        return 1

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("ULTRON")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("ULTRON")

    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(5, 10, 15))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(192, 216, 232))
    palette.setColor(QPalette.ColorRole.Base, QColor(7, 15, 26))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(10, 20, 30))
    palette.setColor(QPalette.ColorRole.Text, QColor(192, 216, 232))
    palette.setColor(QPalette.ColorRole.Button, QColor(13, 31, 60))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 212, 255))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 100, 200))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    # Font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    try:
        import qasync
    except ImportError:
        logger.warning("qasync not installed, using basic async integration: pip install qasync")
        # Fallback: run asyncio in a background thread, Qt in main thread
        return _run_threaded(app, assistant, settings)

    # Run with qasync (preferred - single thread, properly integrated)
    return _run_qasync(app, assistant, settings)


def _run_qasync(app, assistant, settings) -> int:
    """Run with qasync for proper asyncio+Qt integration."""
    import qasync
    from ui.main_window import MainWindow

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    with loop:
        window = MainWindow(assistant=assistant, settings=settings)
        window.show()

        async def _startup():
            if assistant:
                success = await assistant.initialize()
                if success:
                    asyncio.create_task(assistant.run())

        loop.run_until_complete(_startup())
        return loop.run_forever()


def _run_threaded(app, assistant, settings) -> int:
    """
    Fallback: run asyncio in a background thread.
    The asyncio loop handles LLM/voice/tools.
    Qt event loop handles UI.
    Communication via thread-safe signals.
    """
    import threading
    from ui.main_window import MainWindow

    # Create and start asyncio thread
    loop = asyncio.new_event_loop()

    def _run_async():
        asyncio.set_event_loop(loop)
        if assistant:
            loop.run_until_complete(assistant.initialize())
            loop.run_until_complete(assistant.run())
        else:
            loop.run_forever()

    async_thread = threading.Thread(target=_run_async, daemon=True, name="ultron-async")
    async_thread.start()

    # Run Qt in main thread
    window = MainWindow(assistant=assistant, settings=settings)
    window.show()

    exit_code = app.exec()
    loop.call_soon_threadsafe(loop.stop)
    return exit_code
