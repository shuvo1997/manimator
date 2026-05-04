from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QProgressBar, QStatusBar, QWidget, QHBoxLayout


class StatusBar(QStatusBar):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizeGripEnabled(True)

        # Context usage label (left side)
        self._context_label = QLabel("Context: —")
        self._context_label.setToolTip(
            "Tokens used vs. the model's context window limit"
        )

        # Render progress bar + label (right side)
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(180)
        self._progress_bar.setMaximumHeight(14)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()

        self._render_label = QLabel()

        # Assemble left widget
        left = QWidget()
        left_layout = QHBoxLayout(left)
        left_layout.setContentsMargins(4, 0, 4, 0)
        left_layout.addWidget(self._context_label)

        self.addWidget(left, 1)
        self.addPermanentWidget(self._render_label)
        self.addPermanentWidget(self._progress_bar)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_idle(self) -> None:
        self._render_label.setText("Ready")
        self._progress_bar.hide()
        self.clearMessage()

    def set_streaming(self) -> None:
        self._render_label.setText("Generating code…")
        self._progress_bar.hide()

    def set_rendering(self, frame: int, total: int) -> None:
        if total > 0:
            pct = int(frame / total * 100)
            self._render_label.setText(f"Rendering {frame}/{total} ({pct}%)")
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(frame)
            self._progress_bar.show()
        else:
            self._render_label.setText("Rendering…")

    def set_render_done(self) -> None:
        self._render_label.setText("Render complete")
        self._progress_bar.hide()

    def set_error(self, msg: str) -> None:
        truncated = msg[:120] + "…" if len(msg) > 120 else msg
        self._render_label.setText(f"Error: {truncated}")
        self._progress_bar.hide()

    def update_context(self, used: int, limit: int) -> None:
        if limit <= 0:
            self._context_label.setText("Context: —")
            return
        pct = used / limit * 100
        text = f"Context: {used:,} / {limit:,} tokens ({pct:.0f}%)"
        self._context_label.setText(text)

        if pct < 70:
            color = "#4CAF50"  # green
            tooltip = "Context usage is healthy."
        elif pct < 90:
            color = "#FF9800"  # orange
            tooltip = "Approaching context limit. Consider starting a new conversation."
        else:
            color = "#F44336"  # red
            tooltip = "Context nearly full. Oldest messages will be dropped on the next prompt."

        self._context_label.setStyleSheet(f"color: {color};")
        self._context_label.setToolTip(tooltip)
