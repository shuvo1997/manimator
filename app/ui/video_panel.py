from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QFont
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QTabWidget,
)
import re


class _PythonHighlighter(QSyntaxHighlighter):
    """Minimal Python syntax highlighter for the code preview tab."""

    KEYWORDS = (
        "False", "None", "True", "and", "as", "assert", "async", "await",
        "break", "class", "continue", "def", "del", "elif", "else", "except",
        "finally", "for", "from", "global", "if", "import", "in", "is",
        "lambda", "nonlocal", "not", "or", "pass", "raise", "return",
        "try", "while", "with", "yield", "self",
    )

    def __init__(self, document):
        super().__init__(document)

        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#C792EA"))
        kw_fmt.setFontWeight(QFont.Weight.Bold)

        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#C3E88D"))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#546E7A"))
        comment_fmt.setFontItalic(True)

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#F78C6C"))

        func_fmt = QTextCharFormat()
        func_fmt.setForeground(QColor("#82AAFF"))

        self._rules = [
            (re.compile(r"#[^\n]*"), comment_fmt),
            (re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), str_fmt),
            (re.compile(r"'[^'\\]*(\\.[^'\\]*)*'"), str_fmt),
            (re.compile(r"\b(" + "|".join(self.KEYWORDS) + r")\b"), kw_fmt),
            (re.compile(r"\b\d+(\.\d+)?\b"), num_fmt),
            (re.compile(r"\b[A-Za-z_]\w*(?=\s*\()"), func_fmt),
        ]

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


class VideoPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_path: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: none; background: #0F172A; }"
            "QTabBar::tab { background: #1E293B; color: #94A3B8; padding: 6px 16px; }"
            "QTabBar::tab:selected { background: #0F172A; color: #E2E8F0; }"
        )

        # ── Video tab ──────────────────────────────────────────────────────────
        video_container = QWidget()
        video_container.setStyleSheet("background: #000;")
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(0)

        self._video_widget = QVideoWidget()
        self._video_widget.setStyleSheet("background: #000;")

        self._placeholder = QLabel("Animation will appear here")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #475569; font-size: 16px; background: #0F172A;")

        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video_widget)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)

        # Controls row
        controls = QWidget()
        controls.setStyleSheet("background: #1E293B; border-top: 1px solid #334155;")
        ctrl_layout = QHBoxLayout(controls)
        ctrl_layout.setContentsMargins(8, 4, 8, 4)

        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedSize(30, 30)
        self._play_btn.setStyleSheet(
            "QPushButton { background: #334155; color: white; border-radius: 4px; }"
            "QPushButton:hover { background: #475569; }"
        )
        self._play_btn.clicked.connect(self._toggle_play)

        self._seek_bar = QSlider(Qt.Orientation.Horizontal)
        self._seek_bar.setStyleSheet(
            "QSlider::groove:horizontal { background: #334155; height: 4px; }"
            "QSlider::handle:horizontal { background: #2563EB; width: 12px; height: 12px; "
            "margin: -4px 0; border-radius: 6px; }"
        )
        self._seek_bar.sliderMoved.connect(self._on_seek)

        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setStyleSheet("color: #94A3B8; font-size: 11px;")

        self._save_btn = QPushButton("⬇ Save")
        self._save_btn.setFixedHeight(30)
        self._save_btn.setEnabled(False)
        self._save_btn.setStyleSheet(
            "QPushButton { background: #1E3A5F; color: #93C5FD; border-radius: 4px; "
            "padding: 0 10px; font-size: 12px; }"
            "QPushButton:hover { background: #2563EB; color: white; }"
            "QPushButton:disabled { background: #1E293B; color: #475569; }"
        )
        self._save_btn.clicked.connect(self._save_video)

        ctrl_layout.addWidget(self._play_btn)
        ctrl_layout.addWidget(self._seek_bar, 1)
        ctrl_layout.addWidget(self._time_label)
        ctrl_layout.addWidget(self._save_btn)

        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)

        video_layout.addWidget(self._placeholder, 1)
        video_layout.addWidget(self._video_widget, 1)
        self._video_widget.hide()
        video_layout.addWidget(controls)

        # ── Code tab ───────────────────────────────────────────────────────────
        self._code_view = QPlainTextEdit()
        self._code_view.setReadOnly(True)
        self._code_view.setStyleSheet(
            "QPlainTextEdit { background: #0D1117; color: #CDD9E5; "
            "font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace; "
            "font-size: 12px; border: none; padding: 8px; }"
        )
        self._highlighter = _PythonHighlighter(self._code_view.document())

        self._tabs.addTab(video_container, "Video")
        self._tabs.addTab(self._code_view, "Code")

        layout.addWidget(self._tabs)

    # ── Public API ─────────────────────────────────────────────────────────────

    def load_video(self, path: str) -> None:
        self._current_path = path
        self._placeholder.hide()
        self._video_widget.show()
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()
        self._play_btn.setText("⏸")
        self._save_btn.setEnabled(True)
        self._tabs.setCurrentIndex(0)

    def show_code(self, code: str) -> None:
        self._code_view.setPlainText(code)

    def _save_video(self) -> None:
        if not self._current_path:
            return
        src = Path(self._current_path)
        dest, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Animation",
            str(Path.home() / src.name),
            "MP4 Video (*.mp4);;Animated GIF (*.gif)",
        )
        if not dest:
            return

        if selected_filter.startswith("Animated GIF") or dest.endswith(".gif"):
            self._export_gif(str(src), dest)
        else:
            if not dest.endswith(".mp4"):
                dest += ".mp4"
            try:
                shutil.copy2(str(src), dest)
                QMessageBox.information(self, "Saved", f"Video saved to:\n{dest}")
            except Exception as e:
                QMessageBox.critical(self, "Save Failed", str(e))

    def _export_gif(self, src: str, dest: str) -> None:
        if not dest.endswith(".gif"):
            dest += ".gif"
        self._save_btn.setEnabled(False)
        self._save_btn.setText("⟳ Converting…")
        try:
            # Two-pass ffmpeg GIF: palette-based for best quality
            palette = str(Path(dest).with_suffix(".palette.png"))
            r1 = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", src,
                    "-vf", "fps=15,scale=640:-1:flags=lanczos,palettegen",
                    palette,
                ],
                capture_output=True, timeout=60,
            )
            if r1.returncode != 0:
                raise RuntimeError(r1.stderr.decode()[-300:])

            r2 = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", src, "-i", palette,
                    "-filter_complex", "fps=15,scale=640:-1:flags=lanczos[x];[x][1:v]paletteuse",
                    dest,
                ],
                capture_output=True, timeout=120,
            )
            Path(palette).unlink(missing_ok=True)
            if r2.returncode != 0:
                raise RuntimeError(r2.stderr.decode()[-300:])

            size_kb = Path(dest).stat().st_size // 1024
            QMessageBox.information(self, "Saved", f"GIF saved to:\n{dest}\n({size_kb} KB)")
        except FileNotFoundError:
            QMessageBox.critical(
                self, "ffmpeg not found",
                "Install ffmpeg to export GIFs:\n  brew install ffmpeg"
            )
        except Exception as e:
            QMessageBox.critical(self, "GIF Export Failed", str(e))
        finally:
            self._save_btn.setEnabled(True)
            self._save_btn.setText("⬇ Save")

    def show_placeholder(self) -> None:
        self._video_widget.hide()
        self._placeholder.show()

    def set_tab(self, index: int) -> None:
        self._tabs.setCurrentIndex(index)

    # ── Private ────────────────────────────────────────────────────────────────

    def _toggle_play(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self._play_btn.setText("▶")
        else:
            self._player.play()
            self._play_btn.setText("⏸")

    def _on_seek(self, position: int) -> None:
        self._player.setPosition(position)

    def _on_position_changed(self, pos: int) -> None:
        self._seek_bar.setValue(pos)
        self._time_label.setText(
            f"{_fmt_ms(pos)} / {_fmt_ms(self._player.duration())}"
        )

    def _on_duration_changed(self, duration: int) -> None:
        self._seek_bar.setMaximum(duration)

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.InvalidMedia and self._current_path:
            # Try ffmpeg re-encode fallback
            self._try_reencode(self._current_path)

    def _try_reencode(self, path: str) -> None:
        out_path = Path(path).with_suffix(".compat.mp4")
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", path,
                    "-vcodec", "libx264", "-acodec", "aac",
                    "-pix_fmt", "yuv420p",
                    str(out_path),
                ],
                capture_output=True,
                timeout=60,
            )
            if result.returncode == 0 and out_path.exists():
                self._player.setSource(QUrl.fromLocalFile(str(out_path)))
                self._player.play()
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        # Give up — show file path
        self._placeholder.setText(
            f"Cannot play video.\nFile saved at:\n{path}"
        )
        self._video_widget.hide()
        self._placeholder.show()


def _fmt_ms(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"
