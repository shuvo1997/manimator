from __future__ import annotations

import ast
import logging
import re

log = logging.getLogger(__name__)


def _strip_thinking_tags(text: str) -> str:
    """Remove <think>...</think> blocks that thinking models emit."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)


def _trim_trailing_prose(code: str) -> str:
    """
    Remove trailing non-Python lines (prose after the code block).
    Tries progressively shorter versions until ast.parse succeeds.
    Falls back to the original if nothing parses.
    """
    lines = code.splitlines()
    for end in range(len(lines), 0, -1):
        candidate = "\n".join(lines[:end]).strip()
        if not candidate:
            continue
        try:
            ast.parse(candidate)
            return candidate
        except SyntaxError:
            continue
    return code


def extract_code_block(llm_response: str) -> str | None:
    """
    Extract Python code from an LLM response using four strategies:
    1. ```python ... ``` fenced block (case-insensitive language tag)
    2. ``` ... ``` fenced block (no language tag)
    3. Raw Python -- find the first `from manimlib` or `class ... (Scene):` line
       and take everything from there, trimming trailing prose.
    4. Same strategies applied after stripping <think>...</think> blocks.
    """
    cleaned = _strip_thinking_tags(llm_response)

    for pass_num, text in enumerate((llm_response, cleaned), 1):
        # Strategy 1: explicit python fence (case-insensitive)
        match = re.search(r"```[Pp]ython\s*\n(.*?)```", text, re.DOTALL)
        if match:
            log.debug("Strategy 1 (python fence) succeeded on pass %d", pass_num)
            return match.group(1).strip()

        # Strategy 2: generic fence
        match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
        if match:
            log.debug("Strategy 2 (generic fence) succeeded on pass %d", pass_num)
            return match.group(1).strip()

        # Strategy 3: raw Python -- locate the manimlib import or class definition
        lines = text.splitlines()
        start_idx = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("from manimlib") or stripped.startswith("import manimlib"):
                start_idx = i
                break
            if re.match(r"class\s+\w+\s*\(\s*Scene\s*\)", stripped):
                start_idx = i
                break

        if start_idx is not None:
            candidate = "\n".join(lines[start_idx:]).strip()
            if "def construct" in candidate:
                trimmed = _trim_trailing_prose(candidate)
                log.debug("Strategy 3 (raw Python) succeeded on pass %d, start_idx=%d", pass_num, start_idx)
                return trimmed
            else:
                log.debug("Strategy 3: found start at line %d but no 'def construct'", start_idx)
        else:
            log.debug("Strategy 3 pass %d: no manimlib import or Scene class found", pass_num)

    log.warning("All extraction strategies failed. Response length=%d, first 200 chars: %r", len(llm_response), llm_response[:200])
    return None


def ensure_scene_class(code: str, class_name: str = "GeneratedScene") -> str:
    """
    Verify code contains a Scene subclass named class_name.
    If the LLM used a different name, rename it via regex.
    Raises ValueError if no Scene subclass is found.
    """
    if f"class {class_name}(Scene)" in code:
        return code

    pattern = r"class\s+(\w+)\s*\(\s*Scene\s*\)"
    match = re.search(pattern, code)
    if not match:
        raise ValueError(
            "Generated code contains no Scene subclass. "
            "Try rephrasing your prompt."
        )

    original_name = match.group(1)
    code = re.sub(rf"\b{re.escape(original_name)}\b", class_name, code)
    return code
