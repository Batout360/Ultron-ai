"""
ULTRON Chat Message Widget
Displays conversation messages with proper styling.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame, QSizePolicy,
    QScrollArea, QTextEdit
)


STYLE_USER = """
QFrame {
    background-color: #0d1f3c;
    border: 1px solid #1a3a6e;
    border-radius: 12px;
    padding: 4px;
}
"""

STYLE_ASSISTANT = """
QFrame {
    background-color: #071018;
    border: 1px solid #00d4ff33;
    border-radius: 12px;
    padding: 4px;
}
"""

STYLE_SYSTEM = """
QFrame {
    background-color: #0a0a0a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 2px;
}
"""


class MessageWidget(QFrame):
    """A single chat message bubble."""

    def __init__(self, role: str, text: str, parent=None) -> None:
        super().__init__(parent)
        self._role = role
        self._text_label = None
        self._setup(text)

    def _setup(self, text: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Role label
        role_label = QLabel(self._role.upper())
        if self._role == "user":
            role_label.setStyleSheet("color: #4488ff; font-size: 10px; font-weight: bold; font-family: Consolas;")
            self.setStyleSheet(STYLE_USER)
        elif self._role == "assistant":
            role_label.setStyleSheet("color: #00d4ff; font-size: 10px; font-weight: bold; font-family: Consolas;")
            self.setStyleSheet(STYLE_ASSISTANT)
        else:
            role_label.setStyleSheet("color: #666; font-size: 10px; font-family: Consolas;")
            self.setStyleSheet(STYLE_SYSTEM)

        # Text content
        self._text_label = QLabel(text)
        self._text_label.setWordWrap(True)
        self._text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._text_label.setStyleSheet(
            "color: #e0e8f0; font-size: 13px; font-family: 'Segoe UI', sans-serif; line-height: 1.5;"
        )

        layout.addWidget(role_label)
        layout.addWidget(self._text_label)

    def update_text(self, text: str) -> None:
        """Update text content (for streaming)."""
        if self._text_label:
            self._text_label.setText(text)

    def append_text(self, token: str) -> None:
        """Append a token to the message (for streaming)."""
        if self._text_label:
            self._text_label.setText(self._text_label.text() + token)


class ChatWidget(QWidget):
    """
    Scrollable conversation display widget.
    Messages stream in as tokens arrive from the LLM.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._messages: list[MessageWidget] = []
        self._current_assistant_msg: MessageWidget | None = None
        self._setup()

    def _setup(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #0a1520;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #1a4060;
                border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setSpacing(8)
        self._container_layout.setContentsMargins(8, 8, 8, 8)
        self._container_layout.addStretch()

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

    def add_user_message(self, text: str) -> None:
        """Add a complete user message."""
        self._current_assistant_msg = None
        msg = MessageWidget("user", text)
        self._container_layout.insertWidget(
            self._container_layout.count() - 1, msg
        )
        self._messages.append(msg)
        self._scroll_to_bottom()

    def begin_assistant_message(self) -> None:
        """Start a new assistant message that will be filled by streaming tokens."""
        self._current_assistant_msg = MessageWidget("assistant", "")
        self._container_layout.insertWidget(
            self._container_layout.count() - 1,
            self._current_assistant_msg,
        )
        self._messages.append(self._current_assistant_msg)

    def append_token(self, token: str) -> None:
        """Append a streaming token to the current assistant message."""
        if self._current_assistant_msg:
            self._current_assistant_msg.append_text(token)
            self._scroll_to_bottom()

    def finalize_assistant_message(self, text: str) -> None:
        """Set the final complete text of the current assistant message."""
        if self._current_assistant_msg:
            self._current_assistant_msg.update_text(text)
            self._current_assistant_msg = None

    def add_system_message(self, text: str) -> None:
        """Add a system notification message."""
        msg = MessageWidget("system", text)
        self._container_layout.insertWidget(
            self._container_layout.count() - 1, msg
        )
        self._messages.append(msg)
        self._scroll_to_bottom()

    def clear(self) -> None:
        """Clear all messages."""
        for msg in self._messages:
            msg.setParent(None)
        self._messages.clear()
        self._current_assistant_msg = None

    def _scroll_to_bottom(self) -> None:
        scrollbar = self._scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
