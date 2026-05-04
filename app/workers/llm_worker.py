from __future__ import annotations

import logging
import openai
from PyQt6.QtCore import QThread, pyqtSignal

# ── Module-level helper for two-pass layout planning ─────────────────────────

LAYOUT_PLANNING_PROMPT = """\
Before writing any code, describe the visual layout in 3-5 sentences:
- What nodes/elements exist and their values
- How they are positioned on screen (use UP/DOWN/LEFT/RIGHT language, with approximate distances in ManimGL units where the screen is 14 units wide × 8 units tall)
- What edges or connections exist between elements
- What the animation sequence is (what appears first, what moves or changes)
Keep all positions within the safe zone: x ∈ [-5, 5], y ∈ [-2.5, 2.8].
Do NOT write any Python code — only the layout description in plain English.
"""


def get_layout_plan(client: openai.OpenAI, messages: list[dict], model: str) -> str:
    """
    Synchronous single-call LLM request to produce a spatial layout plan.
    Returns the plan text, or empty string on failure.
    """
    log = logging.getLogger(__name__)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages + [{"role": "user", "content": LAYOUT_PLANNING_PROMPT}],
            max_tokens=300,
            stream=False,
        )
        plan = (resp.choices[0].message.content or "").strip()
        log.debug("Layout plan (%d chars): %r", len(plan), plan[:200])
        return plan
    except Exception as exc:
        log.warning("Layout planning call failed: %s", exc)
        return ""

log = logging.getLogger(__name__)

from app.core.tool_calling import (
    RENDER_TOOL,
    accumulate_tool_call_chunks,
    finalize_tool_call,
)


class LLMWorker(QThread):
    token_received = pyqtSignal(str)          # each streamed text token
    stream_complete = pyqtSignal(str)         # full text (no tool call path)
    tool_call_complete = pyqtSignal(str, str) # (code, explanation) via tool call
    usage_updated = pyqtSignal(int, int)      # (prompt_tokens, completion_tokens)
    error_occurred = pyqtSignal(str)          # user-facing error message

    def __init__(
        self,
        client: openai.OpenAI,
        messages: list[dict],
        model: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._messages = messages
        self._model = model
        self._stop_flag = False

    def stop(self) -> None:
        self._stop_flag = True

    def run(self) -> None:
        # Try with tool calling first; fall back to plain text if unsupported.
        full_text, tool_chunks = self._stream(use_tools=True)

        if full_text is None and tool_chunks is None:
            # _stream already emitted an error signal
            return

        # Prefer tool call result
        if tool_chunks:
            result = finalize_tool_call(tool_chunks)
            if result:
                code, explanation = result
                log.debug("Tool call extracted, code length=%d", len(code))
                self.tool_call_complete.emit(code, explanation)
                return

        log.debug(
            "No tool call; full_text length=%d, first 300 chars: %r",
            len(full_text),
            full_text[:300],
        )
        self.stream_complete.emit(full_text)

    # ── Internal ────────────────────────────────────────────────────────────────

    def _stream(
        self, use_tools: bool
    ) -> tuple[str | None, dict | None]:
        """
        Run one streaming request.

        Returns (full_text, tool_chunks) on success.
        Returns (None, None) after emitting error_occurred.

        If the model doesn't support tool calling (OpenRouter 404), retries
        automatically without tools so the fenced-block fallback handles it.
        """
        full_text = ""
        tool_chunks: dict[int, dict] = {}

        kwargs: dict = dict(
            model=self._model,
            messages=self._messages,
            stream=True,
            stream_options={"include_usage": True},
        )
        if use_tools:
            kwargs["tools"] = [RENDER_TOOL]
            kwargs["tool_choice"] = "auto"

        try:
            stream = self._client.chat.completions.create(**kwargs)

            for chunk in stream:
                if self._stop_flag:
                    break

                choice = chunk.choices[0] if chunk.choices else None

                if not chunk.choices and hasattr(chunk, "usage") and chunk.usage:
                    self.usage_updated.emit(
                        chunk.usage.prompt_tokens or 0,
                        chunk.usage.completion_tokens or 0,
                    )
                    continue

                if choice is None:
                    continue

                delta = choice.delta

                if delta.content:
                    full_text += delta.content
                    self.token_received.emit(delta.content)

                if delta.tool_calls:
                    accumulate_tool_call_chunks(tool_chunks, delta)

                if (
                    choice.finish_reason is not None
                    and hasattr(chunk, "usage")
                    and chunk.usage
                ):
                    self.usage_updated.emit(
                        chunk.usage.prompt_tokens or 0,
                        chunk.usage.completion_tokens or 0,
                    )

            return full_text, tool_chunks

        except openai.NotFoundError as exc:
            msg = str(exc)
            if use_tools and "tool use" in msg.lower():
                log.info(
                    "Model %s doesn't support tool calling — retrying without tools",
                    self._model,
                )
                return self._stream(use_tools=False)
            self.error_occurred.emit(f"Model not found: {self._model}\n{msg}")
            return None, None

        except openai.APIConnectionError:
            self.error_occurred.emit(
                "Cannot connect to the LLM server.\n"
                "Make sure Ollama is running (`ollama serve`) or "
                "LM Studio is open with a model loaded."
            )
            return None, None

        except openai.AuthenticationError:
            self.error_occurred.emit(
                "Invalid API key. Check your key in Settings."
            )
            return None, None

        except openai.RateLimitError:
            self.error_occurred.emit(
                "Rate limit exceeded. Wait a moment and try again."
            )
            return None, None

        except Exception as exc:
            self.error_occurred.emit(f"LLM error: {exc}")
            return None, None
