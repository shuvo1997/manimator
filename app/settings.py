from __future__ import annotations

from PyQt6.QtCore import QSettings

from .core.llm_client import BACKENDS, DEFAULT_MODELS


class AppSettings:
    """Thin wrapper around QSettings for cross-platform persistence."""

    def __init__(self) -> None:
        self._s = QSettings("manimator", "manimator")

    # ── LLM Backend ────────────────────────────────────────────────────────────

    @property
    def backend(self) -> str:
        return self._s.value("backend", "ollama")  # type: ignore[return-value]

    @backend.setter
    def backend(self, v: str) -> None:
        self._s.setValue("backend", v)

    @property
    def base_url(self) -> str:
        backend = self.backend
        if backend in BACKENDS:
            return BACKENDS[backend]["url"]
        # custom
        return self._s.value("custom_url", BACKENDS["ollama"]["url"])  # type: ignore[return-value]

    @property
    def api_key(self) -> str:
        backend = self.backend
        if backend in ("ollama", "lmstudio"):
            return BACKENDS[backend]["key"]
        return self._s.value(f"api_key_{backend}", "")  # type: ignore[return-value]

    def set_api_key(self, backend: str, key: str) -> None:
        self._s.setValue(f"api_key_{backend}", key)

    @property
    def custom_url(self) -> str:
        return self._s.value("custom_url", BACKENDS["ollama"]["url"])  # type: ignore[return-value]

    @custom_url.setter
    def custom_url(self, v: str) -> None:
        self._s.setValue("custom_url", v)

    @property
    def model(self) -> str:
        backend = self.backend
        default = DEFAULT_MODELS.get(backend, "")
        return self._s.value(f"model_{backend}", default)  # type: ignore[return-value]

    @model.setter
    def model(self, v: str) -> None:
        self._s.setValue(f"model_{self.backend}", v)

    @property
    def context_length(self) -> int:
        return int(self._s.value("context_length", 8192))  # type: ignore[arg-type]

    @context_length.setter
    def context_length(self, v: int) -> None:
        self._s.setValue("context_length", v)

    # ── Render ─────────────────────────────────────────────────────────────────

    @property
    def quality(self) -> str:
        return self._s.value("quality", "medium")  # type: ignore[return-value]

    @quality.setter
    def quality(self, v: str) -> None:
        self._s.setValue("quality", v)

    @property
    def render_timeout(self) -> int:
        return int(self._s.value("render_timeout", 180))  # type: ignore[arg-type]

    @render_timeout.setter
    def render_timeout(self, v: int) -> None:
        self._s.setValue("render_timeout", v)

    # ── Window geometry ────────────────────────────────────────────────────────

    def save_geometry(self, key: str, data: bytes) -> None:
        self._s.setValue(f"geometry/{key}", data)

    def load_geometry(self, key: str) -> bytes | None:
        return self._s.value(f"geometry/{key}")  # type: ignore[return-value]
