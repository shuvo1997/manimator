#!/usr/bin/env python3
"""
Test OpenRouter API connectivity.

Usage:
    OPENROUTER_API_KEY=sk-or-... python test_openrouter.py
"""
from __future__ import annotations

import os
import sys

import openai

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
BASE_URL = "https://openrouter.ai/api/v1"

# OpenRouter recommends (not required) these headers for attribution / rate-limit tiers
EXTRA_HEADERS = {
    "HTTP-Referer": "https://github.com/manimator",
    "X-Title": "Manimator",
}


def _make_client(api_key: str) -> openai.OpenAI:
    return openai.OpenAI(
        base_url=BASE_URL,
        api_key=api_key,
        default_headers=EXTRA_HEADERS,
    )


def test_list_models(api_key: str) -> list[str]:
    print("\n=== Test: List Models ===")
    client = _make_client(api_key)
    models = client.models.list()
    names = [m.id for m in models.data]
    print(f"  Found {len(names)} models")
    for n in names[:10]:
        print(f"    {n}")
    if len(names) > 10:
        print(f"    ... and {len(names) - 10} more")
    print("  PASS  models listed")
    return names


def test_chat_completion(api_key: str, model: str = "openai/gpt-4o-mini") -> None:
    print(f"\n=== Test: Chat Completion ({model}) ===")
    client = _make_client(api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with exactly: hello world"}],
        max_tokens=20,
    )
    text = response.choices[0].message.content or ""
    print(f"  Response: {text!r}")
    assert "hello" in text.lower() or len(text) > 0, "Empty response"
    print("  PASS  chat completion works")


def test_streaming(api_key: str, model: str = "openai/gpt-4o-mini") -> None:
    print(f"\n=== Test: Streaming ({model}) ===")
    client = _make_client(api_key)
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Count from 1 to 5, space-separated."}],
        max_tokens=30,
        stream=True,
        stream_options={"include_usage": True},
    )
    tokens: list[str] = []
    usage = None
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            tokens.append(chunk.choices[0].delta.content)
        if hasattr(chunk, "usage") and chunk.usage:
            usage = chunk.usage
    full = "".join(tokens)
    print(f"  Streamed: {full!r}")
    print(f"  Usage: {usage}")
    assert full.strip(), "Empty stream"
    print("  PASS  streaming works")


if __name__ == "__main__":
    key = API_KEY or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not key:
        print("ERROR: Set OPENROUTER_API_KEY env var or pass key as first argument")
        print("  Example: OPENROUTER_API_KEY=sk-or-... python test_openrouter.py")
        sys.exit(1)

    print(f"Using key: {key[:10]}...{key[-4:]}")

    try:
        models = test_list_models(key)
        # Pick an affordable model for completion tests
        test_model = "openai/gpt-4o-mini"
        if test_model not in models and models:
            test_model = models[0]
            print(f"  (using {test_model} for completion tests)")
        test_chat_completion(key, test_model)
        test_streaming(key, test_model)
        print("\n" + "=" * 50)
        print("ALL OPENROUTER TESTS PASSED")
    except openai.AuthenticationError as e:
        print(f"\nFAIL  Authentication error: {e}")
        print("  Check your API key at https://openrouter.ai/keys")
        sys.exit(1)
    except openai.APIConnectionError as e:
        print(f"\nFAIL  Connection error: {e}")
        print("  Check your internet connection")
        sys.exit(1)
    except Exception as e:
        print(f"\nFAIL  {type(e).__name__}: {e}")
        sys.exit(1)
