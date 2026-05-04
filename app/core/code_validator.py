from __future__ import annotations

import ast
from dataclasses import dataclass, field

FORBIDDEN_IMPORTS: frozenset[str] = frozenset([
    "os", "subprocess", "sys", "shutil", "socket", "requests",
    "urllib", "http", "ftplib", "smtplib", "importlib", "builtins",
    "ctypes", "cffi", "multiprocessing", "threading", "asyncio",
    "pathlib", "tempfile", "glob", "io", "pickle", "shelve",
])

ALLOWED_IMPORTS: frozenset[str] = frozenset([
    "manimlib", "numpy", "math", "random", "colorsys", "itertools",
    "functools", "typing", "collections", "enum", "abc",
    "dataclasses", "copy", "operator",
])

FORBIDDEN_BUILTINS: frozenset[str] = frozenset([
    "eval", "exec", "open", "__import__", "compile", "globals",
    "locals", "vars", "getattr", "setattr", "delattr",
])


@dataclass
class ValidationResult:
    is_safe: bool = True
    violations: list[str] = field(default_factory=list)


def validate_code(code: str) -> ValidationResult:
    """
    AST-based safety pre-scan. Best-effort; not a security boundary.
    The user is consenting to run their own local LLM's output.
    """
    result = ValidationResult()

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        result.is_safe = False
        result.violations.append(f"SyntaxError: {exc}")
        return result

    for node in ast.walk(tree):
        # Check import statements
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in FORBIDDEN_IMPORTS:
                    result.is_safe = False
                    result.violations.append(f"Forbidden import: {alias.name}")
                elif top not in ALLOWED_IMPORTS:
                    result.is_safe = False
                    result.violations.append(f"Unrecognized import: {alias.name}")

        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module in FORBIDDEN_IMPORTS:
                result.is_safe = False
                result.violations.append(f"Forbidden import: from {node.module}")
            elif module and module not in ALLOWED_IMPORTS:
                result.is_safe = False
                result.violations.append(f"Unrecognized import: from {node.module}")

        # Check calls to forbidden builtins
        elif isinstance(node, ast.Call):
            func_name = _get_func_name(node.func)
            if func_name in FORBIDDEN_BUILTINS:
                result.is_safe = False
                result.violations.append(f"Forbidden call: {func_name}()")

    return result


def _get_func_name(func_node: ast.expr) -> str:
    if isinstance(func_node, ast.Name):
        return func_node.id
    if isinstance(func_node, ast.Attribute):
        return func_node.attr
    return ""
