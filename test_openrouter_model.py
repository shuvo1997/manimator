#!/usr/bin/env python3
"""
Diagnose which model OpenRouter actually uses for a request.

Usage:
    OPENROUTER_API_KEY=sk-or-... python test_openrouter_model.py [model-id]
"""
from __future__ import annotations

import os
import sys
import openai

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_HEADERS = {
    "HTTP-Referer": "https://github.com/manimator",
    "X-Title": "Manimator",
}

SIMPLE_TOOL = {
    "type": "function",
    "function": {
        "name": "render_animation",
        "description": "Render a ManimGL animation",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "explanation": {"type": "string"},
            },
            "required": ["code", "explanation"],
        },
    },
}


def make_client(key: str) -> openai.OpenAI:
    return openai.OpenAI(
        base_url=BASE_URL,
        api_key=key,
        default_headers=DEFAULT_HEADERS,
    )


def list_free_models(client: openai.OpenAI) -> list[str]:
    print("\n=== Available Free Models (:free suffix) ===")
    models = client.models.list()
    free = sorted(m.id for m in models.data if ":free" in m.id)
    for m in free:
        print(f"  {m}")
    print(f"  Total: {len(free)}")
    return free


def test_plain(client: openai.OpenAI, model: str) -> None:
    print(f"\n=== Test 1: Plain chat (no tools) — {model} ===")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            max_tokens=10,
        )
        used = resp.model
        content = resp.choices[0].message.content or ""
        print(f"  Requested : {model}")
        print(f"  Used      : {used}")
        print(f"  Response  : {content!r}")
        if used != model:
            print(f"  ⚠  REROUTED to {used}")
        else:
            print(f"  ✓  Correct model used")
    except openai.NotFoundError as e:
        print(f"  ✗  Model not found: {e}")
    except openai.RateLimitError as e:
        print(f"  ✗  Rate limited: {e}")
    except Exception as e:
        print(f"  ✗  {type(e).__name__}: {e}")


def test_with_tools_auto(client: openai.OpenAI, model: str) -> None:
    print(f"\n=== Test 2: tools + tool_choice=auto (current app behaviour) — {model} ===")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            tools=[SIMPLE_TOOL],
            tool_choice="auto",
            max_tokens=30,
        )
        used = resp.model
        finish = resp.choices[0].finish_reason
        content = resp.choices[0].message.content or ""
        tool_calls = resp.choices[0].message.tool_calls or []
        print(f"  Requested   : {model}")
        print(f"  Used        : {used}")
        print(f"  finish_reason: {finish}")
        print(f"  Content     : {content!r}")
        print(f"  Tool calls  : {len(tool_calls)}")
        if used != model:
            print(f"  ⚠  REROUTED — this is why you see a different model being charged!")
        else:
            print(f"  ✓  Correct model used")
    except openai.NotFoundError as e:
        print(f"  ✗  Model not found: {e}")
    except openai.RateLimitError as e:
        print(f"  ✗  Rate limited (correct model is being used but it's rate-limited): {e}")
    except Exception as e:
        print(f"  ✗  {type(e).__name__}: {e}")


def test_without_tools(client: openai.OpenAI, model: str) -> None:
    print(f"\n=== Test 3: No tools at all (fenced-block path) — {model} ===")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            max_tokens=10,
        )
        used = resp.model
        content = resp.choices[0].message.content or ""
        print(f"  Requested : {model}")
        print(f"  Used      : {used}")
        print(f"  Response  : {content!r}")
        if used != model:
            print(f"  ⚠  REROUTED even without tools")
        else:
            print(f"  ✓  Works — app should skip tools for this model")
    except openai.NotFoundError as e:
        print(f"  ✗  Model not found: {e}")
    except openai.RateLimitError as e:
        print(f"  ✗  Rate limited: {e}")
    except Exception as e:
        print(f"  ✗  {type(e).__name__}: {e}")


if __name__ == "__main__":
    key = API_KEY or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not key:
        print("ERROR: Set OPENROUTER_API_KEY or pass as first argument")
        sys.exit(1)

    client = make_client(key)
    free_models = list_free_models(client)

    # Pick model from args, else first available free model
    if len(sys.argv) > 2:
        model = sys.argv[2]
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("sk-"):
        model = sys.argv[1]
    elif free_models:
        model = free_models[0]
        print(f"\nNo model specified — using first free model: {model}")
    else:
        print("\nNo free models found and no model specified. Exiting.")
        sys.exit(1)

    test_plain(client, model)
    test_with_tools_auto(client, model)
    test_without_tools(client, model)

    print("\n" + "=" * 60)
    print("DONE — if Test 2 shows REROUTED, the fix is to disable")
    print("tool_choice for models that don't support tool calling.")
