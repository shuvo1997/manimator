from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QToolBar,
    QWidget,
)

from .core.code_extractor import extract_code_block, ensure_scene_class
from .core.code_postprocessor import postprocess as postprocess_code
from .core.conversation import ConversationStore
from .core.example_library import detect_category, get_example
from .core.llm_client import check_health, create_client
from .core.mistake_memory import (
    MistakeMemory,
    build_fix_prompt,
    build_fix_hint,
    classify_error,
    extract_bad_pattern,
)
from .core.render_pipeline import RenderPipeline
from .prompts.system_prompt import SYSTEM_PROMPT
from .settings import AppSettings
from .ui.chat_panel import ChatPanel, AssistantBubble, RetryBubble
from .ui.settings_dialog import SettingsDialog
from .ui.status_bar import StatusBar
from .ui.video_panel import VideoPanel
from .workers.llm_worker import LLMWorker, get_layout_plan
from .workers.render_worker import RenderWorker

# Categories that trigger the two-pass layout-planning step
_STRUCTURAL_CATEGORIES = {"tree", "graph", "dp"}

MAX_AUTO_RETRIES = 3


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._settings = AppSettings()
        self._store = ConversationStore()
        self._pipeline = RenderPipeline()
        self._mistake_memory = MistakeMemory()

        self._current_conv_id: int = self._store.new_conversation()
        self._last_assistant_msg_id: int | None = None
        self._last_code: str | None = None
        self._current_bubble: AssistantBubble | None = None
        self._current_retry_bubble: RetryBubble | None = None

        # Retry state
        self._retry_count: int = 0
        self._original_prompt: str = ""

        self._llm_worker: LLMWorker | None = None
        self._render_worker: RenderWorker | None = None

        self._build_ui()
        self._connect_signals()
        self._restore_geometry()

        QTimer.singleShot(200, self._check_llm_health)

    # ── UI Construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowTitle("Manimator")
        self.setMinimumSize(900, 600)

        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet(
            "QToolBar { background: #1E293B; border-bottom: 1px solid #334155; spacing: 4px; padding: 2px 8px; }"
        )

        title_action = QAction("Manimator", self)
        title_action.setEnabled(False)
        toolbar.addAction(title_action)

        spacer = QWidget()
        from PyQt6.QtWidgets import QSizePolicy
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        settings_action = QAction("⚙ Settings", self)
        settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(settings_action)

        new_chat_action = QAction("＋ New Chat", self)
        new_chat_action.triggered.connect(self._new_conversation)
        toolbar.addAction(new_chat_action)

        self.addToolBar(toolbar)
        toolbar.setStyleSheet(
            "QToolBar { background: #1E293B; border-bottom: 1px solid #334155; }"
            "QToolButton { color: #E2E8F0; padding: 4px 10px; }"
            "QToolButton:hover { background: #334155; border-radius: 4px; }"
            "QToolButton:disabled { color: #64748B; font-weight: bold; font-size: 14px; }"
        )

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setStyleSheet("QSplitter { background: #0F172A; }")
        self._splitter.setHandleWidth(4)

        self._chat_panel = ChatPanel()
        self._video_panel = VideoPanel()

        self._splitter.addWidget(self._chat_panel)
        self._splitter.addWidget(self._video_panel)
        self._splitter.setStretchFactor(0, 35)
        self._splitter.setStretchFactor(1, 65)

        self.setCentralWidget(self._splitter)

        self._status_bar = StatusBar()
        self.setStatusBar(self._status_bar)

        self.setStyleSheet(
            "QMainWindow { background: #0F172A; }"
            "QWidget { color: #E2E8F0; }"
        )

    def _connect_signals(self) -> None:
        self._chat_panel.prompt_submitted.connect(self.on_send_prompt)
        self._chat_panel.render_again_btn.clicked.connect(self._render_again)

    # ── Slots ──────────────────────────────────────────────────────────────────

    def on_send_prompt(self, prompt: str) -> None:
        # Reset retry state for fresh prompts
        self._retry_count = 0
        self._original_prompt = prompt
        self._current_retry_bubble = None

        self._chat_panel.set_input_enabled(False)
        self._chat_panel.add_user_message(prompt)
        self._store.add_message(self._current_conv_id, "user", prompt)

        self._start_llm_request(user_prompt=prompt)

    def _start_llm_request(self, user_prompt: str = "") -> None:
        """
        Build message list and fire a new LLMWorker.

        For structural prompts (tree/graph/dp), first runs a short synchronous
        layout-planning call and injects the plan into the message context
        (Strategy 3 — Two-Pass Generation).
        """
        messages, was_truncated = self._store.build_messages_for_request(
            self._current_conv_id,
            self._build_system_prompt(user_prompt or self._original_prompt),
            self._settings.context_length,
        )
        if was_truncated:
            self._chat_panel.add_error_bubble(
                "⚠ Earlier messages were removed to fit the context window. "
                "Start a new conversation to reset."
            )

        client = create_client(self._settings.base_url, self._settings.api_key)

        # Strategy 3 — Two-Pass Generation for structural prompts
        effective_prompt = user_prompt or self._original_prompt
        category = detect_category(effective_prompt) if effective_prompt else None
        if category in _STRUCTURAL_CATEGORIES and self._retry_count == 0:
            # Show "Planning layout…" in the bubble while running the sync planning call
            self._current_bubble = self._chat_panel.add_assistant_bubble()
            self._current_bubble.set_planning_label()
            self._status_bar.set_streaming()

            # Synchronous layout plan (short, fast call — ~250 tokens)
            layout_plan = get_layout_plan(client, messages, self._settings.model)
            if layout_plan:
                # Inject the plan as a prior assistant turn so the LLM follows it
                messages = messages + [
                    {
                        "role": "assistant",
                        "content": (
                            f"Layout plan for this animation:\n{layout_plan}\n\n"
                            "Now I will write the complete ManimGL code following this layout exactly."
                        ),
                    }
                ]
                self._current_bubble.clear_planning_label()
        else:
            self._current_bubble = self._chat_panel.add_assistant_bubble()
            self._status_bar.set_streaming()

        self._llm_worker = LLMWorker(client, messages, self._settings.model)
        self._llm_worker.token_received.connect(self._on_token_received)
        self._llm_worker.stream_complete.connect(self._on_stream_complete)
        self._llm_worker.tool_call_complete.connect(self._on_tool_call_complete)
        self._llm_worker.usage_updated.connect(self._on_usage_updated)
        self._llm_worker.error_occurred.connect(self._on_llm_error)
        self._llm_worker.start()

    def _build_system_prompt(self, user_prompt: str = "") -> str:
        """
        Build the system prompt by appending:
        1. A category-specific verified example snippet (if the prompt matches a known category)
        2. Learned mistakes from previous sessions
        """
        base = SYSTEM_PROMPT

        # Strategy 1 — dynamic example injection
        if user_prompt:
            example = get_example(user_prompt)
            if example:
                base += (
                    "\n\n═══════════════════════════════════════════════════════════\n"
                    "RELEVANT VERIFIED PATTERN FOR THIS REQUEST — follow exactly\n"
                    "═══════════════════════════════════════════════════════════\n"
                    + example
                )

        # Append learned mistakes
        learned = self._mistake_memory.format_for_prompt()
        if learned:
            base += (
                "\n\n═══════════════════════════════════════════════════════════\n"
                "MISTAKES LEARNED FROM PREVIOUS SESSIONS — NEVER REPEAT THESE\n"
                "═══════════════════════════════════════════════════════════\n"
                + learned
            )
        return base

    def _on_token_received(self, token: str) -> None:
        if self._current_bubble:
            self._current_bubble.append_token(token)
            self._chat_panel.scroll_to_bottom()

    def _on_stream_complete(self, full_response: str) -> None:
        if self._current_bubble:
            self._current_bubble.finalize()

        code = extract_code_block(full_response)
        if not code:
            self._chat_panel.add_error_bubble(
                "The LLM response contained no code block.\n"
                "Try rephrasing your prompt."
            )
            self._finish_generation()
            return

        try:
            code = ensure_scene_class(code)
        except ValueError as exc:
            self._chat_panel.add_error_bubble(str(exc))
            self._finish_generation()
            return

        # Strategy 2 — deterministic post-processing fixes
        code = postprocess_code(code)

        self._handle_code(code, explanation="")
        self._save_assistant_message(full_response, code)

    def _on_tool_call_complete(self, code: str, explanation: str) -> None:
        if self._current_bubble:
            self._current_bubble.finalize(
                explanation or "Animation code generated. Rendering…"
            )

        try:
            code = ensure_scene_class(code)
        except ValueError as exc:
            self._chat_panel.add_error_bubble(str(exc))
            self._finish_generation()
            return

        # Strategy 2 — deterministic post-processing fixes
        code = postprocess_code(code)

        self._handle_code(code, explanation)
        self._save_assistant_message(explanation or code, code)

    def _handle_code(self, code: str, explanation: str) -> None:
        self._last_code = code
        self._video_panel.show_code(code)
        self._video_panel.set_tab(1)
        self._start_render(code)

    def _save_assistant_message(self, content: str, code: str) -> None:
        msg_id = self._store.add_message(
            self._current_conv_id,
            "assistant",
            content,
            code_snippet=code,
        )
        self._last_assistant_msg_id = msg_id

    def _start_render(self, code: str) -> None:
        self._render_worker = RenderWorker(
            code,
            self._settings.quality,
            self._settings.render_timeout,
            self._pipeline,
        )
        self._render_worker.progress.connect(self._on_render_progress)
        self._render_worker.render_complete.connect(self._on_render_complete)
        self._render_worker.error_occurred.connect(self._on_render_error)
        self._render_worker.start()

    def _on_render_progress(self, frame: int, total: int) -> None:
        self._status_bar.set_rendering(frame, total)

    def _on_render_complete(self, video_path: str) -> None:
        # Mark retry bubble as success if one is active
        if self._current_retry_bubble:
            self._current_retry_bubble.mark_success(self._retry_count)
            self._current_retry_bubble = None

        self._video_panel.load_video(video_path)
        self._status_bar.set_render_done()
        self._chat_panel.set_render_again_enabled(True)
        if self._last_assistant_msg_id is not None:
            self._store.update_video_path(self._last_assistant_msg_id, video_path)
        self._finish_generation()

    def _on_render_error(self, user_msg: str, raw_stderr: str) -> None:
        """Handle a render failure — attempt auto-fix up to MAX_AUTO_RETRIES times."""
        # Classify the error and record the mistake
        error_type = classify_error(raw_stderr)
        bad_pattern = extract_bad_pattern(raw_stderr)
        fix_hint = build_fix_hint(error_type, bad_pattern, raw_stderr)

        if bad_pattern:
            self._mistake_memory.record(bad_pattern, error_type, fix_hint)

        # Save error to conversation so LLM sees it on retry
        self._store.add_message(
            self._current_conv_id,
            "assistant",
            f"[Render error — {error_type}]\n{raw_stderr[-600:]}",
        )

        if self._retry_count < MAX_AUTO_RETRIES and self._last_code:
            self._retry_count += 1

            # Update or create the retry bubble
            if self._current_retry_bubble:
                self._current_retry_bubble._label.setText(
                    f"⟳  Auto-fixing render error — attempt {self._retry_count}/{MAX_AUTO_RETRIES}…"
                )
                self._current_retry_bubble._set_style("retry")
            else:
                self._current_retry_bubble = self._chat_panel.add_retry_bubble(
                    self._retry_count, MAX_AUTO_RETRIES
                )

            # Build fix-request message and save to DB
            fix_msg = build_fix_prompt(self._last_code, raw_stderr, self._retry_count)
            self._store.add_message(self._current_conv_id, "user", fix_msg)

            self._status_bar.set_streaming()
            self._start_llm_request()  # retry uses _original_prompt via default
        else:
            # Exhausted retries
            if self._current_retry_bubble:
                self._current_retry_bubble.mark_failed()
                self._current_retry_bubble = None

            hint = fix_hint
            self._chat_panel.add_error_bubble(
                f"Render failed after {self._retry_count} attempt(s).\n\n"
                f"{user_msg[:400]}\n\n"
                f"💡 {hint}"
            )
            self._status_bar.set_error("Render failed")
            self._finish_generation()

    def _on_llm_error(self, msg: str) -> None:
        if self._current_bubble:
            self._current_bubble.finalize("(error)")
        self._chat_panel.add_error_bubble(msg)
        self._status_bar.set_error("LLM error")
        self._finish_generation()

    def _on_usage_updated(self, prompt_tokens: int, _completion_tokens: int) -> None:
        self._status_bar.update_context(prompt_tokens, self._settings.context_length)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _finish_generation(self) -> None:
        self._chat_panel.set_input_enabled(True)
        self._current_bubble = None
        if not self._render_worker or not self._render_worker.isRunning():
            self._status_bar.set_idle()

    def _render_again(self) -> None:
        if self._last_code:
            self._retry_count = 0
            self._current_retry_bubble = None
            self._chat_panel.set_render_again_rendering()
            self._chat_panel.set_input_enabled(False)
            self._status_bar.set_rendering(0, 0)
            self._start_render(self._last_code)

    def _check_llm_health(self) -> None:
        available, models = check_health(
            self._settings.base_url,
            self._settings.api_key,
            timeout=3.0,
        )
        if not available:
            backend = self._settings.backend
            if backend == "ollama":
                tip = "Start Ollama with: `ollama serve`"
            elif backend == "lmstudio":
                tip = "Open LM Studio and load a model."
            elif backend in ("openrouter", "huggingface"):
                tip = "Check your API key in Settings."
            else:
                tip = "Check your backend URL in Settings."
            self._chat_panel.show_warning_banner(
                f"No LLM detected at {self._settings.base_url}.\n{tip}"
            )
        elif models and not self._settings.model:
            self._settings.model = models[0]

    def _new_conversation(self) -> None:
        self._current_conv_id = self._store.new_conversation()
        self._last_code = None
        self._last_assistant_msg_id = None
        self._retry_count = 0
        self._current_retry_bubble = None
        self._chat_panel.clear_history()
        self._video_panel.show_placeholder()
        self._status_bar.set_idle()
        self._chat_panel.set_render_again_enabled(False)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self._settings, self)
        if dialog.exec():
            QTimer.singleShot(0, self._refresh_context_length)

    def _refresh_context_length(self) -> None:
        check_health(self._settings.base_url, self._settings.api_key, timeout=3.0)

    # ── Geometry persistence ───────────────────────────────────────────────────

    def _restore_geometry(self) -> None:
        geom = self._settings.load_geometry("window")
        if geom:
            self.restoreGeometry(geom)
        state = self._settings.load_geometry("splitter")
        if state:
            self._splitter.restoreState(state)

    def closeEvent(self, event) -> None:
        self._settings.save_geometry("window", self.saveGeometry().data())
        self._settings.save_geometry("splitter", self._splitter.saveState().data())
        super().closeEvent(event)
