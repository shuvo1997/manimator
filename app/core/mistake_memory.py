from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

log = logging.getLogger(__name__)

_DEFAULT_PATH = Path.home() / ".manimator" / "learned_mistakes.json"


@dataclass
class Mistake:
    bad_pattern: str   # the API name or pattern that caused the error
    error_type: str    # e.g. "NameError", "AttributeError"
    fix_hint: str      # what to use instead


class MistakeMemory:
    """
    Persistent store of ManimGL API mistakes the LLM has made.
    Loaded on startup, injected into the system prompt so the LLM
    never repeats a known bad pattern.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_PATH
        self._mistakes: dict[str, Mistake] = {}
        self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    def record(self, bad_pattern: str, error_type: str, fix_hint: str) -> None:
        """Store a new mistake. Silently ignores duplicates."""
        if bad_pattern in self._mistakes:
            return
        self._mistakes[bad_pattern] = Mistake(bad_pattern, error_type, fix_hint)
        self._save()
        log.info("Recorded new mistake: %s — %s", bad_pattern, fix_hint)

    def format_for_prompt(self) -> str:
        """Return a block of text ready to append to the system prompt."""
        if not self._mistakes:
            return ""
        lines = [
            f"❌ DO NOT use `{m.bad_pattern}` — caused {m.error_type}. {m.fix_hint}"
            for m in self._mistakes.values()
        ]
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._mistakes)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for item in data:
                m = Mistake(**item)
                self._mistakes[m.bad_pattern] = m
            log.debug("Loaded %d learned mistakes from %s", len(self._mistakes), self._path)
        except Exception as exc:
            log.warning("Could not load mistake memory: %s", exc)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps([asdict(m) for m in self._mistakes.values()], indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            log.warning("Could not save mistake memory: %s", exc)


# ── Error parsing helpers (used by MainWindow) ────────────────────────────────

def classify_error(stderr: str) -> str:
    if "NameError" in stderr:
        return "NameError"
    if "ModuleNotFoundError" in stderr or "ImportError" in stderr:
        return "ImportError"
    if "SyntaxError" in stderr:
        return "SyntaxError"
    if "TypeError" in stderr:
        return "TypeError"
    if "AttributeError" in stderr:
        return "AttributeError"
    if "IndentationError" in stderr:
        return "IndentationError"
    return "RuntimeError"


def extract_bad_pattern(stderr: str) -> str | None:
    """Pull the offending name out of common Python error messages."""
    # NameError: name 'GrowFromCenter' is not defined
    m = re.search(r"NameError: name '(\w+)' is not defined", stderr)
    if m:
        return m.group(1)
    # AttributeError: 'Circle' object has no attribute 'grow'
    m = re.search(r"AttributeError: .+ has no attribute '(\w+)'", stderr)
    if m:
        return m.group(1)
    # ModuleNotFoundError: No module named 'xxx'
    m = re.search(r"No module named '([\w.]+)'", stderr)
    if m:
        return m.group(1)
    return None


def build_fix_hint(error_type: str, bad_pattern: str | None, stderr: str) -> str:
    if error_type == "NameError" and bad_pattern:
        return (
            f"`{bad_pattern}` does not exist in ManimGL 1.7. "
            "Check the API reference in the system prompt and use the correct equivalent."
        )
    if error_type == "ImportError" and bad_pattern:
        return f"Install the missing package with: pip install {bad_pattern.split('.')[0]}"
    if error_type == "AttributeError" and bad_pattern:
        return (
            f"`.{bad_pattern}()` is not a valid ManimGL method. "
            "Remove it or replace with a method from the API reference."
        )
    if error_type == "SyntaxError":
        return "The generated code has a Python syntax error. Check indentation and brackets."
    if error_type == "TypeError":
        return (
            "A wrong argument type was passed to a ManimGL function. "
            "Check the API reference for correct argument types."
        )
    return "Check the Code tab for details and try rephrasing your prompt."


def build_fix_prompt(failed_code: str, stderr: str, attempt: int) -> str:
    """Construct the user message sent to the LLM to request a fix."""
    return (
        f"[Auto-fix attempt {attempt}] The previous animation code failed to render.\n\n"
        f"Error:\n```\n{stderr[-800:]}\n```\n\n"
        f"Broken code:\n```python\n{failed_code}\n```\n\n"
        f"Instructions:\n"
        f"- Fix ALL errors shown above\n"
        f"- The FIRST line MUST be: from manimlib import *\n"
        f"- Only use API names listed in the system prompt reference\n"
        f"- Return the complete corrected code"
    )
