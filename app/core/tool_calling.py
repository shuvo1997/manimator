from __future__ import annotations

import json

RENDER_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "render_animation",
        "description": (
            "Render a ManimGL animation from Python code. "
            "Call this tool with the complete ManimGL scene code."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": (
                        "Complete Python source for a ManimGL GeneratedScene(Scene) class. "
                        "Must start with `from manimlib import *` and define "
                        "`class GeneratedScene(Scene)` with a `construct(self)` method."
                    ),
                },
                "explanation": {
                    "type": "string",
                    "description": "1-2 sentence plain-English description of the animation.",
                },
            },
            "required": ["code", "explanation"],
        },
    },
}


def extract_from_tool_call(message) -> tuple[str, str] | None:
    """
    Given a ChatCompletionMessage, return (code, explanation) if the LLM
    called render_animation, otherwise return None.
    """
    if not message.tool_calls:
        return None
    for tc in message.tool_calls:
        if tc.function.name == "render_animation":
            try:
                args = json.loads(tc.function.arguments)
                code = args.get("code", "").strip()
                explanation = args.get("explanation", "").strip()
                if code:
                    return code, explanation
            except (json.JSONDecodeError, AttributeError):
                return None
    return None


def accumulate_tool_call_chunks(chunks_so_far: dict, delta) -> None:
    """
    Accumulates streamed tool-call delta chunks into chunks_so_far dict.
    Mutates chunks_so_far in-place.

    chunks_so_far structure: {index: {"name": str, "arguments": str}}
    """
    if not delta.tool_calls:
        return
    for tc_chunk in delta.tool_calls:
        idx = tc_chunk.index
        if idx not in chunks_so_far:
            chunks_so_far[idx] = {"name": "", "arguments": ""}
        if tc_chunk.function:
            if tc_chunk.function.name:
                chunks_so_far[idx]["name"] += tc_chunk.function.name
            if tc_chunk.function.arguments:
                chunks_so_far[idx]["arguments"] += tc_chunk.function.arguments


def finalize_tool_call(chunks_so_far: dict) -> tuple[str, str] | None:
    """
    After streaming is complete, attempt to extract (code, explanation)
    from accumulated chunks. Returns None if not a render_animation call.
    """
    for _idx, tc in chunks_so_far.items():
        if tc["name"] == "render_animation":
            try:
                args = json.loads(tc["arguments"])
                code = args.get("code", "").strip()
                explanation = args.get("explanation", "").strip()
                if code:
                    return code, explanation
            except (json.JSONDecodeError, KeyError):
                return None
    return None
