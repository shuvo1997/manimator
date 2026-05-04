"""
Code post-processor — applies deterministic fixes to LLM-generated ManimGL code
before it is sent to the renderer.

Fixes applied in order:
1. Ensure `import numpy as np` is present when `np.` is used
2. Strip `if __name__ == "__main__":` block
3. Ensure `construct` ends with `self.wait(2)` if none present
4. Inject `make_edge` helper when tree/graph pattern detected but helper absent
5. Warn (log) if out-of-viewport literal coordinates detected

None of these changes should break valid code; each guard is conservative.
"""
from __future__ import annotations

import ast
import logging
import re

log = logging.getLogger(__name__)


# ── Public entry point ────────────────────────────────────────────────────────

def postprocess(code: str) -> str:
    """Apply all fixes and return the cleaned code."""
    code = _ensure_numpy_import(code)
    code = _strip_main_block(code)
    code = _ensure_trailing_wait(code)
    code = _inject_make_edge_if_needed(code)
    _warn_out_of_viewport(code)
    return code


# ── Fix 1: numpy import ───────────────────────────────────────────────────────

def _ensure_numpy_import(code: str) -> str:
    """If `np.` is used but `import numpy as np` is absent, insert it."""
    if "np." not in code:
        return code
    if re.search(r"\bimport numpy as np\b", code):
        return code

    # Insert after `from manimlib import *` if present, else at the top
    insert_line = "import numpy as np"
    manimlib_match = re.search(r"^from manimlib import \*[ \t]*$", code, re.MULTILINE)
    if manimlib_match:
        pos = manimlib_match.end()
        code = code[:pos] + "\n" + insert_line + code[pos:]
    else:
        code = insert_line + "\n" + code

    log.debug("code_postprocessor: inserted numpy import")
    return code


# ── Fix 2: strip __main__ block ───────────────────────────────────────────────

_MAIN_BLOCK_RE = re.compile(
    r'\nif\s+__name__\s*==\s*["\']__main__["\']\s*:.*',
    re.DOTALL,
)


def _strip_main_block(code: str) -> str:
    """Remove `if __name__ == '__main__':` and everything after it."""
    result = _MAIN_BLOCK_RE.sub("", code)
    if result != code:
        log.debug("code_postprocessor: stripped __main__ block")
    return result


# ── Fix 3: trailing self.wait ─────────────────────────────────────────────────

def _ensure_trailing_wait(code: str) -> str:
    """
    If `construct` exists and has no `self.wait(` call anywhere in its body,
    append `        self.wait(2)` before the last outdented line / end of class.
    """
    if "def construct" not in code:
        return code
    if "self.wait(" in code:
        return code  # already has a wait somewhere — leave it

    # Append before the last line that is at class level or end of file.
    # Strategy: find the last non-empty line and add wait before the class
    # definition ends. This is conservative — we append at the end of the file.
    stripped = code.rstrip()
    code = stripped + "\n        self.wait(2)\n"
    log.debug("code_postprocessor: appended self.wait(2)")
    return code


# ── Fix 4: make_edge helper injection ────────────────────────────────────────

_MAKE_EDGE_HELPER = '''\
        # ── Auto-injected make_edge helper ────────────────────────────
        def _make_node(val, color=__import__("manimlib.constants", fromlist=["BLUE_E"]).BLUE_E):
            from manimlib import Circle, Text, VGroup, WHITE
            c = Circle(radius=0.42, color=WHITE)
            c.set_fill(color, opacity=0.85)
            lbl = Text(str(val), font_size=28, color=WHITE).move_to(c)
            return VGroup(c, lbl)

        def _make_edge(n1, n2, color=None):
            import numpy as _np
            from manimlib import Line, GREY_B
            if color is None:
                color = GREY_B
            s, e = n1.get_center(), n2.get_center()
            d = e - s
            ln = _np.linalg.norm(d)
            if ln < 1e-9:
                return Line(s, e, color=color)
            u = d / ln
            gap = 0.46
            return Line(s + u * gap, e - u * gap, color=color, stroke_width=2)
        # ── End auto-injected helper ───────────────────────────────────
'''


def _inject_make_edge_if_needed(code: str) -> str:
    """
    If the code:
      - Builds Circle-based nodes AND
      - Uses Arrow/Line arguments that look like node-to-node calls AND
      - Does NOT already define a `make_edge` or `_make_edge` function
    then inject a safe `_make_edge` helper into the top of `construct`.

    This is conservative: only injects when confident the pattern is present.
    """
    # Already has a helper
    if "def make_edge" in code or "def _make_edge" in code:
        return code

    has_circle = "Circle(" in code
    # Look for Arrow/Line(node_var.get_center or Arrow(node1, node2) patterns
    has_node_arrow = bool(
        re.search(r"Arrow\s*\(\s*\w+\s*[,.]", code)
        or re.search(r"Line\s*\(\s*\w+\s*[,.]", code)
    )
    # Only inject for tree/graph-style code (has both Circle nodes and arrows)
    if not (has_circle and has_node_arrow):
        return code

    # Inject at the very start of the construct body (right after `def construct(self):`)
    construct_match = re.search(r"(def construct\(self\)\s*:\n)", code)
    if not construct_match:
        return code

    pos = construct_match.end()
    code = code[:pos] + _MAKE_EDGE_HELPER + code[pos:]
    log.debug("code_postprocessor: injected make_edge helper")
    return code


# ── Fix 5: out-of-viewport warning ───────────────────────────────────────────

# ManimGL default frame: width=14.22, height=8.0 units
# Safe zone we enforce: x ∈ [-6.5, 6.5], y ∈ [-3.8, 3.8]
_FLOAT_RE = re.compile(r"[-+]?\d+\.?\d*")
_POSITION_CALL_RE = re.compile(
    r"(?:move_to|shift|to_edge|next_to|ORIGIN\s*\+|UP\s*\*|DOWN\s*\*|LEFT\s*\*|RIGHT\s*\*).*",
)


def _warn_out_of_viewport(code: str) -> None:
    """Log a warning if large coordinate literals (> 7) are found."""
    # Simple heuristic: find standalone large numbers used in positioning contexts
    for line in code.splitlines():
        # Skip comment lines
        if line.lstrip().startswith("#"):
            continue
        nums = [float(m) for m in _FLOAT_RE.findall(line) if _looks_like_coord(m)]
        for n in nums:
            if abs(n) > 7.0:
                log.warning(
                    "code_postprocessor: possible out-of-viewport coordinate %.1f "
                    "in line: %r",
                    n,
                    line.strip()[:80],
                )
                break  # one warning per line is enough


def _looks_like_coord(s: str) -> bool:
    """Return True if the string looks like a standalone coordinate literal."""
    try:
        v = float(s)
    except ValueError:
        return False
    # Ignore very small numbers (likely probabilities) and obviously non-coord values
    if abs(v) < 1.5:
        return False
    # Ignore what look like font sizes or counts (large round integers)
    if v == int(v) and v > 20:
        return False
    return True
