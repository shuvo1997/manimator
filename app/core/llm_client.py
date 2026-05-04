from __future__ import annotations

import openai

BACKENDS: dict[str, dict[str, str]] = {
    "ollama": {
        "url": "http://localhost:11434/v1",
        "key": "ollama",
    },
    "lmstudio": {
        "url": "http://localhost:1234/v1",
        "key": "lm-studio",
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1",
        "key": "",
    },
    "huggingface": {
        "url": "https://api-inference.huggingface.co/v1",
        "key": "",
    },
}

DEFAULT_MODELS: dict[str, str] = {
    "ollama": "qwen2.5-coder:32b",
    "lmstudio": "Qwen2.5-Coder-32B-Instruct",
    "openrouter": "anthropic/claude-3.5-sonnet",
    "huggingface": "Qwen/Qwen2.5-Coder-32B-Instruct",
}

# Popular OpenRouter models for the dropdown (fetched lazily from /v1/models, but
# these serve as sensible defaults when the API call fails or hasn't been made yet)
OPENROUTER_POPULAR_MODELS = [
    # Free tier (50 req/day shared across all free models)
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "qwen/qwen3-coder:free",
    # Paid — good for code generation
    "anthropic/claude-sonnet-4-5",
    "anthropic/claude-3.5-haiku",
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "google/gemini-2.0-flash-001",
    "qwen/qwen-2.5-coder-32b-instruct",
    "deepseek/deepseek-r1",
    "meta-llama/llama-3.3-70b-instruct",
]

HUGGINGFACE_POPULAR_MODELS = [
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct",
    "meta-llama/Meta-Llama-3.1-70B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
]


_OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://github.com/manimator",
    "X-Title": "Manimator",
}


def create_client(base_url: str, api_key: str) -> openai.OpenAI:
    headers = _OPENROUTER_HEADERS if "openrouter.ai" in base_url else {}
    return openai.OpenAI(
        base_url=base_url,
        api_key=api_key or "none",
        default_headers=headers,
    )


def check_health(base_url: str, api_key: str, timeout: float = 3.0) -> tuple[bool, list[str]]:
    """Returns (is_available, model_name_list). Never raises."""
    try:
        client = create_client(base_url, api_key)
        models = client.models.list()
        names = [m.id for m in models.data]
        return True, names
    except Exception:
        return False, []
