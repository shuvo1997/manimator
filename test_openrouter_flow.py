#!/usr/bin/env python3
"""
Simulate the full Manimator flow against OpenRouter free models.

Finds which free models can actually generate ManimGL code, then runs the
complete pipeline: prompt → LLM → extract code → render to MP4.

Usage:
    OPENROUTER_API_KEY=sk-or-... python test_openrouter_flow.py
    OPENROUTER_API_KEY=sk-or-... python test_openrouter_flow.py --model google/gemma-3-4b-it:free
    OPENROUTER_API_KEY=sk-or-... python test_openrouter_flow.py --scan   # scan all free models
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import openai

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
BASE_URL = "https://openrouter.ai/api/v1"
EXTRA_HEADERS = {"HTTP-Referer": "https://github.com/manimator", "X-Title": "Manimator"}

# Free models known to be chat/code capable (skip OCR, image, embedding models)
KNOWN_GOOD_FREE_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "google/gemma-3-4b-it:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-3-27b-it:free",
    "qwen/qwen3-8b:free",
    "qwen/qwen3-14b:free",
    "qwen/qwen3-30b-a3b:free",
    "mistralai/mistral-7b-instruct:free",
    "deepseek/deepseek-r1-0528:free",
    "microsoft/phi-4-reasoning:free",
    "nousresearch/deephermes-3-llama-3-8b-preview:free",
]

# Skip models that are obviously not chat models
SKIP_KEYWORDS = [
    "ocr", "embed", "vision", "image", "whisper", "tts",
    "rerank", "clip", "stable", "diffusion",
]

SIMPLE_PROMPT = (
    "Write a ManimGL animation in Python. "
    "Output ONLY a Python code block with no explanation. "
    "The code must start with `from manimlib import *` and define "
    "`class GeneratedScene(Scene)` with a `construct(self)` method that draws a blue circle. "
    "Wrap it in ```python ... ```."
)


def make_client(key: str) -> openai.OpenAI:
    return openai.OpenAI(base_url=BASE_URL, api_key=key, default_headers=EXTRA_HEADERS)


def get_free_models(client: openai.OpenAI) -> list[str]:
    models = client.models.list()
    ids = sorted(m.id for m in models.data)
    free = []
    for mid in ids:
        if ":free" not in mid:
            continue
        low = mid.lower()
        if any(kw in low for kw in SKIP_KEYWORDS):
            continue
        free.append(mid)
    return free


def test_model(client: openai.OpenAI, model: str) -> tuple[bool, str]:
    """
    Returns (success, detail_message).
    Tries without tools first (safest for free models).
    """
    try:
        start = time.time()
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert ManimGL programmer. "
                        "Always output complete Python code in ```python``` blocks."
                    ),
                },
                {"role": "user", "content": SIMPLE_PROMPT},
            ],
            max_tokens=600,
            temperature=0.1,
        )
        elapsed = time.time() - start
        used_model = resp.model
        content = resp.choices[0].message.content or ""

        # Check if the response contains a python code block
        has_code = "```python" in content or "from manimlib import" in content
        has_scene = "GeneratedScene" in content or "class" in content

        if not content.strip():
            return False, f"Empty response (used={used_model}, {elapsed:.1f}s)"

        if not has_code:
            snippet = content[:120].replace("\n", " ")
            return False, f"No code block returned: {snippet!r} (used={used_model})"

        if not has_scene:
            return False, f"Code missing GeneratedScene class (used={used_model})"

        return True, f"OK — {len(content)} chars, {elapsed:.1f}s (used={used_model})"

    except openai.NotFoundError as e:
        return False, f"404 Not Found: {e}"
    except openai.RateLimitError as e:
        return False, f"Rate limited: {e}"
    except openai.BadRequestError as e:
        return False, f"Bad request: {e}"
    except Exception as e:
        msg = str(e)
        if "502" in msg or "Provider returned error" in msg:
            return False, f"502 Provider error (model not suitable for chat)"
        return False, f"{type(e).__name__}: {msg[:200]}"


def run_full_pipeline(client: openai.OpenAI, model: str) -> None:
    """Run the complete app flow: LLM → extract code → render."""
    print(f"\n{'='*60}")
    print(f"FULL PIPELINE TEST — {model}")
    print("=" * 60)

    # Step 1: LLM call
    print("\n[1/3] Calling LLM...")
    ok, detail = test_model(client, model)
    print(f"  {'✓' if ok else '✗'}  {detail}")
    if not ok:
        print("  Aborting pipeline — LLM step failed.")
        return

    # Step 2: Extract code
    print("\n[2/3] Extracting code...")
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert ManimGL programmer. "
                    "Always output complete Python code in ```python``` blocks."
                ),
            },
            {"role": "user", "content": SIMPLE_PROMPT},
        ],
        max_tokens=600,
        temperature=0.1,
    )
    content = resp.choices[0].message.content or ""

    sys.path.insert(0, os.path.dirname(__file__))
    from app.core.code_extractor import extract_code_block, ensure_scene_class

    code = extract_code_block(content)
    if not code:
        print("  ✗  extract_code_block returned None")
        print(f"  Raw response:\n{content[:400]}")
        return
    print(f"  ✓  Extracted {len(code)} chars of code")

    try:
        code = ensure_scene_class(code)
        print("  ✓  ensure_scene_class passed")
    except ValueError as e:
        print(f"  ✗  ensure_scene_class: {e}")
        return

    # Step 3: Render
    print("\n[3/3] Rendering with manimgl...")
    from app.core.render_pipeline import RenderPipeline, ValidationError

    pipeline = RenderPipeline()
    try:
        scene_file, temp_dir = pipeline.prepare_scene_file(code)
    except ValidationError as e:
        print(f"  ✗  Validation: {e.violations}")
        return
    except Exception as e:
        print(f"  ✗  prepare_scene_file: {e}")
        return

    import subprocess
    cmd = pipeline.build_command(scene_file, "low")
    print(f"  Command: {' '.join(str(c) for c in cmd)}")

    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(temp_dir), timeout=120
    )
    combined = result.stdout + result.stderr
    if result.returncode != 0:
        print(f"  ✗  manimgl exited {result.returncode}")
        print(f"  Last 500 chars of output:\n{combined[-500:]}")
        return

    try:
        video = pipeline.parse_output_path(combined, "", temp_dir)
        size_kb = video.stat().st_size // 1024
        print(f"  ✓  Video rendered: {video}  ({size_kb} KB)")
        print(f"\n✅  FULL PIPELINE PASSED for {model}")
    except FileNotFoundError as e:
        print(f"  ✗  Could not find output video: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="", help="Specific model to test")
    parser.add_argument("--scan", action="store_true", help="Scan all free models for chat capability")
    args = parser.parse_args()

    key = API_KEY
    if not key:
        print("ERROR: Set OPENROUTER_API_KEY env var")
        sys.exit(1)

    client = make_client(key)

    if args.scan:
        # Scan all free models and show which ones work
        print("Fetching all free models from OpenRouter...")
        free_models = get_free_models(client)
        print(f"Found {len(free_models)} free chat-capable models\n")

        working = []
        for model in free_models:
            ok, detail = test_model(client, model)
            status = "✓" if ok else "✗"
            print(f"  {status}  {model:<55}  {detail}")
            if ok:
                working.append(model)
            time.sleep(0.5)  # avoid hammering the API

        print(f"\n{'='*60}")
        print(f"WORKING FREE MODELS ({len(working)}/{len(free_models)}):")
        for m in working:
            print(f"  {m}")

    elif args.model:
        run_full_pipeline(client, args.model)

    else:
        # Quick scan of known-good models, then full pipeline on the first one that works
        print("Testing known chat-capable free models...\n")
        working_model = None
        for model in KNOWN_GOOD_FREE_MODELS:
            ok, detail = test_model(client, model)
            status = "✓" if ok else "✗"
            print(f"  {status}  {model:<55}  {detail}")
            if ok and not working_model:
                working_model = model

        if working_model:
            run_full_pipeline(client, working_model)
        else:
            print("\n✗  No working free models found in the known-good list.")
            print("   Run with --scan to check all available free models.")
