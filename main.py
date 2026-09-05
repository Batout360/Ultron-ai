#!/usr/bin/env python3
# main.py — ULTRON AI Command Center entry point
# Pure Holographic Orange Edition

import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore    import Qt
from PySide6.QtGui     import QColor, QPalette, QFont

import theme as C
from ui.main_window import MainWindow


def build_palette() -> QPalette:
    """Dark near-black palette so system widgets don't bleed default greys."""
    pal = QPalette()
    bg  = QColor(C.COLOR_BG)
    fg  = QColor(C.COLOR_TEXT_HI)
    acc = QColor(C.COLOR_PRIMARY)

    for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base,
                 QPalette.ColorRole.AlternateBase):
        pal.setColor(role, bg)

    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.BrightText):
        pal.setColor(role, fg)

    pal.setColor(QPalette.ColorRole.Highlight,     acc)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(C.COLOR_BG))
    pal.setColor(QPalette.ColorRole.Button,        QColor(C.COLOR_BG_PANEL))
    pal.setColor(QPalette.ColorRole.ButtonText,    fg)

    return pal


def main():
    # High-DPI scaling
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    app = QApplication(sys.argv)
    app.setApplicationName(C.APP_NAME)
    app.setApplicationVersion(C.APP_VERSION)

    # Dark application palette
    app.setPalette(build_palette())

    # Global stylesheet — remove any default widget chrome
    app.setStyleSheet(f"""
        QMainWindow, QWidget {{
            background-color: {C.COLOR_BG};
            color: {C.COLOR_TEXT_HI};
            font-family: {C.FONT_MONO};
        }}
        QScrollBar:vertical {{
            background: {C.COLOR_BG};
            width: 4px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background: {C.COLOR_DIM};
            border-radius: 2px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QToolTip {{
            background-color: {C.COLOR_BG_PANEL};
            color: {C.COLOR_TEXT_HI};
            border: 1px solid {C.COLOR_PRIMARY};
        }}
    """)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
