from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


# ── Shared bubble base ─────────────────────────────────────────────────────────

class _BubbleWidget(QFrame):
    """A single chat message bubble."""

    def __init__(self, text: str, is_user: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_user = is_user
        self.setObjectName("userBubble" if is_user else "assistantBubble")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        if is_user:
            self._label.setAlignment(Qt.AlignmentFlag.AlignRight)
            layout.addStretch()
            layout.addWidget(self._label)
            self.setStyleSheet(
                "QFrame#userBubble { background: #2563EB; border-radius: 10px; }"
                "QLabel { color: white; }"
            )
        else:
            self._label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(self._label)
            layout.addStretch()
            self.setStyleSheet(
                "QFrame#assistantBubble { background: #1E293B; border-radius: 10px; }"
                "QLabel { color: #E2E8F0; }"
            )

    def append_text(self, text: str) -> None:
        self._label.setText(self._label.text() + text)


# ── Think section (collapsible) ────────────────────────────────────────────────

class _ThinkSection(QWidget):
    """
    Collapsible block shown when the LLM emits <think>...</think> content.
    Collapsed by default once reasoning is complete.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(2)

        self._toggle_btn = QPushButton("💭 Thinking…")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(
            "QPushButton { color: #64748B; font-size: 11px; font-style: italic; "
            "text-align: left; padding: 2px 0px; border: none; background: transparent; }"
            "QPushButton:hover { color: #94A3B8; }"
        )
        self._toggle_btn.clicked.connect(self._toggle)

        self._content = QLabel()
        self._content.setWordWrap(True)
        self._content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._content.setStyleSheet(
            "QLabel { color: #475569; font-size: 11px; font-style: italic; "
            "background: #0A1628; border-left: 2px solid #334155; "
            "padding: 6px 8px; margin-left: 2px; }"
        )
        self._content.hide()

        layout.addWidget(self._toggle_btn)
        layout.addWidget(self._content)

        self._text = ""
        self._expanded = False
        self._done = False
        self.hide()

    # ── Public ─────────────────────────────────────────────────────────────────

    def update_streaming(self, text: str) -> None:
        """Called while still inside the <think> block."""
        self._text = text
        self._content.setText(text)
        self.show()
        n = len(text)
        self._toggle_btn.setText(
            f"💭 Thinking… ({n} chars) {'▼' if self._expanded else '▶'}"
        )

    def finalize(self, text: str) -> None:
        """Called when </think> is found — reasoning complete, auto-collapse."""
        self._text = text
        self._content.setText(text)
        self._done = True
        n = len(text)
        self._toggle_btn.setText(f"💭 Reasoning complete ({n} chars) ▶")
        # Auto-collapse when done
        self._content.hide()
        self._expanded = False
        self.show()

    # ── Private ────────────────────────────────────────────────────────────────

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        n = len(self._text)
        label = "Reasoning complete" if self._done else "Thinking…"
        arrow = "▼" if self._expanded else "▶"
        self._toggle_btn.setText(f"💭 {label} ({n} chars) {arrow}")
        if self._expanded:
            self._content.show()
        else:
            self._content.hide()


# ── Assistant bubble ───────────────────────────────────────────────────────────

class AssistantBubble(QFrame):
    """
    Streaming assistant response bubble with:
    - "Connecting…" animated loader before first token arrives
    - Collapsible <think> section for reasoning models
    - Live streaming text with cursor indicator
    """

    _DOTS = ["", ".", "..", "..."]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("assistantBubble")
        self.setStyleSheet(
            "QFrame#assistantBubble { background: #1E293B; border-radius: 10px; }"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        inner_widget = QWidget()
        inner_widget.setStyleSheet("background: transparent;")
        inner = QVBoxLayout(inner_widget)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(4)

        # Think section (hidden until <think> tag arrives)
        self._think = _ThinkSection()
        inner.addWidget(self._think)

        # Main response label
        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._label.setStyleSheet("QLabel { color: #E2E8F0; background: transparent; }")
        inner.addWidget(self._label)

        outer.addWidget(inner_widget, 1)
        outer.addStretch(0)

        # Streaming state
        self._raw = ""          # full accumulated text including <think> tags
        self._first_token = True
        self._dot_idx = 0

        # Animated "Connecting…" loader (fires before first token)
        self._loader = QTimer(self)
        self._loader.setInterval(400)
        self._loader.timeout.connect(self._tick_loader)
        self._loader.start()
        self._label.setText("Connecting…")
        self._label.setStyleSheet(
            "QLabel { color: #64748B; font-style: italic; background: transparent; }"
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_planning_label(self) -> None:
        """Show 'Planning layout…' while the two-pass layout call is in progress."""
        self._loader.stop()
        self._label.setText("🗺 Planning layout…")
        self._label.setStyleSheet(
            "QLabel { color: #7DD3FC; font-style: italic; background: transparent; }"
        )

    def clear_planning_label(self) -> None:
        """Reset back to the Connecting… loader after layout plan is received."""
        self._label.setText("Connecting…")
        self._label.setStyleSheet(
            "QLabel { color: #64748B; font-style: italic; background: transparent; }"
        )
        self._dot_idx = 0
        self._loader.start()

    def append_token(self, token: str) -> None:
        if self._first_token:
            self._first_token = False
            self._loader.stop()
            self._label.setStyleSheet(
                "QLabel { color: #E2E8F0; background: transparent; }"
            )

        self._raw += token
        self._render()

    def finalize(self, final_text: str | None = None) -> None:
        """Stop streaming. Optionally replace content with explanation text."""
        self._loader.stop()
        self._label.setStyleSheet(
            "QLabel { color: #E2E8F0; background: transparent; }"
        )
        if final_text is not None:
            self._think.hide()
            self._label.setText(final_text)
            return

        # Strip cursor and finalize think section
        self._raw = self._raw.rstrip("▌")
        self._render(cursor=False)

    # ── Private ────────────────────────────────────────────────────────────────

    def _tick_loader(self) -> None:
        self._dot_idx = (self._dot_idx + 1) % len(self._DOTS)
        self._label.setText(f"Connecting{self._DOTS[self._dot_idx]}")

    def _render(self, cursor: bool = True) -> None:
        """
        Parse self._raw and update think section + main label.

        Handles three states:
          1. No <think> tag at all           → show raw in main label
          2. <think> opened, not yet closed  → think section streaming, main label empty/pre-think
          3. <think>…</think> complete block → think section finalized, main label shows rest
        """
        raw = self._raw

        if "<think>" not in raw:
            # Simple case — no think tags
            self._think.hide()
            self._label.setText(raw + ("▌" if cursor else ""))
            return

        before, _, after_open = raw.partition("<think>")

        if "</think>" not in after_open:
            # Still inside think block
            think_text = after_open.rstrip("▌")
            self._think.update_streaming(think_text)
            pre = before.strip()
            self._label.setText((pre + "\n" if pre else "") + ("▌" if cursor else ""))
        else:
            # Think block complete
            think_text, _, main_text = after_open.partition("</think>")
            self._think.finalize(think_text.strip())
            main = main_text.lstrip("\n")
            self._label.setText(main + ("▌" if cursor else ""))


# ── Other bubble types ─────────────────────────────────────────────────────────

class ErrorBubble(QFrame):
    def __init__(self, message: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        label = QLabel(message)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)
        self.setStyleSheet(
            "QFrame { background: #7F1D1D; border-radius: 10px; border: 1px solid #EF4444; }"
            "QLabel { color: #FCA5A5; }"
        )


class RetryBubble(QFrame):
    """Shown while the LLM is auto-fixing a render failure."""

    def __init__(self, attempt: int, max_attempts: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        self._label = QLabel(f"⟳  Auto-fixing render error — attempt {attempt}/{max_attempts}…")
        self._label.setWordWrap(True)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._label)
        self._set_style("retry")

    def mark_success(self, attempt: int) -> None:
        self._label.setText(f"✓  Fixed on attempt {attempt}")
        self._set_style("success")

    def mark_failed(self) -> None:
        self._label.setText("✗  Auto-fix exhausted all attempts")
        self._set_style("failed")

    def _set_style(self, state: str) -> None:
        if state == "retry":
            self.setStyleSheet(
                "QFrame { background: #1C3A5E; border-radius: 10px; border: 1px solid #3B82F6; }"
                "QLabel { color: #93C5FD; font-style: italic; }"
            )
        elif state == "success":
            self.setStyleSheet(
                "QFrame { background: #14532D; border-radius: 10px; border: 1px solid #22C55E; }"
                "QLabel { color: #86EFAC; }"
            )
        else:
            self.setStyleSheet(
                "QFrame { background: #7F1D1D; border-radius: 10px; border: 1px solid #EF4444; }"
                "QLabel { color: #FCA5A5; }"
            )


class WarningBanner(QFrame):
    dismissed = pyqtSignal()

    def __init__(self, message: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        label = QLabel(message)
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setFlat(True)
        close_btn.clicked.connect(self._dismiss)
        layout.addWidget(label)
        layout.addWidget(close_btn)
        self.setStyleSheet(
            "QFrame { background: #78350F; border-radius: 6px; }"
            "QLabel { color: #FDE68A; }"
            "QPushButton { color: #FDE68A; }"
        )

    def _dismiss(self) -> None:
        self.hide()
        self.dismissed.emit()


# ── Prompt input ───────────────────────────────────────────────────────────────

class _PromptInput(QTextEdit):
    submit_requested = pyqtSignal(str)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if (
            e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and not (e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        ):
            text = self.toPlainText().strip()
            if text:
                self.submit_requested.emit(text)
                self.clear()
        else:
            super().keyPressEvent(e)


# ── Chat panel ─────────────────────────────────────────────────────────────────

class ChatPanel(QWidget):
    prompt_submitted = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._banner: WarningBanner | None = None

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: #0F172A; }")

        self._bubbles_container = QWidget()
        self._bubbles_container.setStyleSheet("background: #0F172A;")
        self._bubbles_layout = QVBoxLayout(self._bubbles_container)
        self._bubbles_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._bubbles_layout.setSpacing(8)
        self._bubbles_layout.setContentsMargins(10, 10, 10, 10)
        self._scroll.setWidget(self._bubbles_container)

        # Input area
        input_frame = QFrame()
        input_frame.setStyleSheet(
            "QFrame { background: #1E293B; border-top: 1px solid #334155; }"
        )
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(8, 8, 8, 8)
        input_layout.setSpacing(6)

        self._input = _PromptInput()
        self._input.setPlaceholderText(
            "Describe an algorithm or paste code to visualize…\n"
            "(Enter to send, Shift+Enter for newline)"
        )
        self._input.setFixedHeight(90)
        self._input.setStyleSheet(
            "QTextEdit { background: #0F172A; color: #E2E8F0; "
            "border: 1px solid #334155; border-radius: 6px; padding: 6px; "
            "font-size: 13px; }"
        )
        self._input.submit_requested.connect(self.prompt_submitted)

        btn_row = QHBoxLayout()

        self._send_btn = QPushButton("Send")
        self._send_btn.setFixedHeight(32)
        self._send_btn.setStyleSheet(
            "QPushButton { background: #2563EB; color: white; border-radius: 6px; "
            "font-weight: bold; padding: 0 16px; }"
            "QPushButton:hover { background: #1D4ED8; }"
            "QPushButton:disabled { background: #475569; }"
        )
        self._send_btn.clicked.connect(self._on_send_clicked)

        self._render_again_btn = QPushButton("Render Again")
        self._render_again_btn.setFixedHeight(32)
        self._render_again_btn.setEnabled(False)
        self._render_again_btn.setStyleSheet(
            "QPushButton { background: #475569; color: white; border-radius: 6px; "
            "padding: 0 12px; }"
            "QPushButton:hover { background: #64748B; }"
            "QPushButton:disabled { background: #334155; color: #64748B; }"
        )

        btn_row.addWidget(self._send_btn)
        btn_row.addWidget(self._render_again_btn)
        btn_row.addStretch()

        input_layout.addWidget(self._input)
        input_layout.addLayout(btn_row)

        outer.addWidget(self._scroll, 1)
        outer.addWidget(input_frame)

    # ── Public API ─────────────────────────────────────────────────────────────

    def add_user_message(self, text: str) -> None:
        bubble = _BubbleWidget(text, is_user=True)
        self._bubbles_layout.addWidget(bubble)
        self._scroll_to_bottom()

    def add_assistant_bubble(self) -> AssistantBubble:
        bubble = AssistantBubble()
        self._bubbles_layout.addWidget(bubble)
        self._scroll_to_bottom()
        return bubble

    def add_error_bubble(self, message: str) -> None:
        bubble = ErrorBubble(message)
        self._bubbles_layout.addWidget(bubble)
        self._scroll_to_bottom()

    def add_retry_bubble(self, attempt: int, max_attempts: int) -> RetryBubble:
        bubble = RetryBubble(attempt, max_attempts)
        self._bubbles_layout.addWidget(bubble)
        self._scroll_to_bottom()
        return bubble

    def show_warning_banner(self, message: str) -> None:
        if self._banner:
            self._banner.hide()
        self._banner = WarningBanner(message, self)
        self._bubbles_layout.insertWidget(0, self._banner)
        self._banner.show()

    def scroll_to_bottom(self) -> None:
        """Public: deferred scroll — call after each streamed token."""
        self._scroll_to_bottom()

    def set_input_enabled(self, enabled: bool) -> None:
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)

    def set_render_again_enabled(self, enabled: bool) -> None:
        self._render_again_btn.setEnabled(enabled)
        if enabled:
            self._render_again_btn.setText("Render Again")
            self._render_again_btn.setStyleSheet(
                "QPushButton { background: #475569; color: white; border-radius: 6px; "
                "padding: 0 12px; }"
                "QPushButton:hover { background: #64748B; }"
                "QPushButton:disabled { background: #334155; color: #64748B; }"
            )

    def set_render_again_rendering(self) -> None:
        self._render_again_btn.setEnabled(False)
        self._render_again_btn.setText("⟳ Rendering…")
        self._render_again_btn.setStyleSheet(
            "QPushButton { background: #1C3A5E; color: #93C5FD; border-radius: 6px; "
            "padding: 0 12px; font-style: italic; }"
            "QPushButton:disabled { background: #1C3A5E; color: #93C5FD; }"
        )

    @property
    def render_again_btn(self) -> QPushButton:
        return self._render_again_btn

    def clear_history(self) -> None:
        while self._bubbles_layout.count():
            item = self._bubbles_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    # ── Private ────────────────────────────────────────────────────────────────

    def _on_send_clicked(self) -> None:
        text = self._input.toPlainText().strip()
        if text:
            self.prompt_submitted.emit(text)
            self._input.clear()

    def _scroll_to_bottom(self) -> None:
        # Defer until Qt has recalculated the layout height, then scroll.
        QTimer.singleShot(0, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))
