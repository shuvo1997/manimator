from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.llm_client import (
    BACKENDS,
    DEFAULT_MODELS,
    HUGGINGFACE_POPULAR_MODELS,
    OPENROUTER_POPULAR_MODELS,
    check_health,
    create_client,
)
from app.settings import AppSettings

BACKEND_LABELS = {
    "ollama": "Ollama (localhost:11434)",
    "lmstudio": "LM Studio (localhost:1234)",
    "openrouter": "OpenRouter (cloud)",
    "huggingface": "Hugging Face (cloud)",
    "custom": "Custom URL",
}

QUALITY_LABELS = ["Low (480p)", "Medium (720p)", "High (1080p)"]
QUALITY_KEYS = ["low", "medium", "high"]


class _ModelFetcher(QThread):
    models_ready = pyqtSignal(list)

    def __init__(self, base_url: str, api_key: str) -> None:
        super().__init__()
        self._url = base_url
        self._key = api_key

    def run(self) -> None:
        try:
            # Use create_client so OpenRouter headers are included automatically
            client = create_client(self._url, self._key)
            models_page = client.models.list()
            names = sorted(m.id for m in models_page.data)
            self.models_ready.emit(names)
        except Exception:
            self.models_ready.emit([])


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._fetcher: _ModelFetcher | None = None
        self._all_models: list[str] = []   # full unfiltered list for search
        self._initializing = True
        self.setWindowTitle("Settings")
        self.setMinimumWidth(600)
        self._build_ui()
        self._load_values()
        self._initializing = False

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── LLM Backend ────────────────────────────────────────────────────────
        llm_group = QGroupBox("LLM Backend")
        form = QFormLayout(llm_group)

        self._backend_combo = QComboBox()
        for key, label in BACKEND_LABELS.items():
            self._backend_combo.addItem(label, key)
        self._backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        form.addRow("Backend:", self._backend_combo)

        self._api_key_label = QLabel("API Key:")
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("Paste your API key here")
        # When the key changes, refresh models for cloud backends
        self._api_key_edit.editingFinished.connect(self._on_api_key_changed)
        form.addRow(self._api_key_label, self._api_key_edit)

        self._custom_url_label = QLabel("Base URL:")
        self._custom_url_edit = QLineEdit()
        self._custom_url_edit.setPlaceholderText("http://localhost:11434/v1")
        form.addRow(self._custom_url_label, self._custom_url_edit)

        # ── Model selection widget ──────────────────────────────────────────────
        model_widget = QWidget()
        model_vbox = QVBoxLayout(model_widget)
        model_vbox.setContentsMargins(0, 0, 0, 0)
        model_vbox.setSpacing(4)

        # Search bar (shown only for cloud backends with many models)
        self._search_label = QLabel("Search models:")
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Type to filter models…")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._filter_models)
        form.addRow(self._search_label, self._search_edit)

        # Combo + Refresh
        model_h = QHBoxLayout()
        model_h.setContentsMargins(0, 0, 0, 0)

        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.setMinimumWidth(360)
        self._model_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._model_combo.setMinimumContentsLength(30)

        self._refresh_btn = QPushButton("↻ Refresh")
        self._refresh_btn.setFixedWidth(90)
        self._refresh_btn.clicked.connect(self._load_models)

        model_h.addWidget(self._model_combo, 1)
        model_h.addWidget(self._refresh_btn)
        model_vbox.addLayout(model_h)

        self._model_status = QLabel("")
        self._model_status.setStyleSheet("color: #94A3B8; font-size: 11px;")
        model_vbox.addWidget(self._model_status)

        form.addRow("Model:", model_widget)
        layout.addWidget(llm_group)

        # ── Render Settings ─────────────────────────────────────────────────────
        render_group = QGroupBox("Render Settings")
        render_form = QFormLayout(render_group)

        self._quality_combo = QComboBox()
        for label in QUALITY_LABELS:
            self._quality_combo.addItem(label)
        render_form.addRow("Video Quality:", self._quality_combo)

        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(30, 600)
        self._timeout_spin.setSuffix(" seconds")
        render_form.addRow("Render Timeout:", self._timeout_spin)

        layout.addWidget(render_group)

        # ── Data ────────────────────────────────────────────────────────────────
        data_group = QGroupBox("Data")
        data_layout = QVBoxLayout(data_group)
        clear_btn = QPushButton("Clear Conversation History")
        clear_btn.setStyleSheet("QPushButton { color: #EF4444; }")
        clear_btn.clicked.connect(self._clear_history)
        data_layout.addWidget(clear_btn)
        layout.addWidget(data_group)

        # ── Buttons ─────────────────────────────────────────────────────────────
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ── Value loading ───────────────────────────────────────────────────────────

    def _load_values(self) -> None:
        backend = self._settings.backend
        for i in range(self._backend_combo.count()):
            if self._backend_combo.itemData(i) == backend:
                self._backend_combo.setCurrentIndex(i)
                break

        self._on_backend_changed(self._backend_combo.currentIndex())

        model = self._settings.model
        if model:
            self._model_combo.setCurrentText(model)

        quality = self._settings.quality
        if quality in QUALITY_KEYS:
            self._quality_combo.setCurrentIndex(QUALITY_KEYS.index(quality))

        self._timeout_spin.setValue(self._settings.render_timeout)
        self._load_models()

    def _on_backend_changed(self, _index: int) -> None:
        backend = self._backend_combo.currentData()
        is_cloud = backend in ("openrouter", "huggingface")
        is_custom = backend == "custom"
        is_openrouter = backend == "openrouter"

        self._api_key_label.setVisible(is_cloud)
        self._api_key_edit.setVisible(is_cloud)
        self._custom_url_label.setVisible(is_custom)
        self._custom_url_edit.setVisible(is_custom)
        self._search_label.setVisible(is_openrouter)
        self._search_edit.setVisible(is_openrouter)
        if not is_openrouter:
            self._search_edit.clear()

        if is_cloud:
            self._api_key_edit.setText(self._settings.api_key)

        if is_custom:
            self._custom_url_edit.setText(self._settings.custom_url)

        # Seed combo with static popular list immediately so there's something to show
        self._model_combo.clear()
        self._all_models = []
        if backend == "openrouter":
            self._model_combo.addItems(OPENROUTER_POPULAR_MODELS)
        elif backend == "huggingface":
            self._model_combo.addItems(HUGGINGFACE_POPULAR_MODELS)

        default = DEFAULT_MODELS.get(backend, "")
        if default:
            self._model_combo.setCurrentText(default)

        if not getattr(self, "_initializing", True):
            self._load_models()

    def _on_api_key_changed(self) -> None:
        """Re-fetch models when the user finishes editing the API key."""
        backend = self._backend_combo.currentData()
        if backend in ("openrouter", "huggingface"):
            self._load_models()

    # ── Model fetching ──────────────────────────────────────────────────────────

    def _load_models(self) -> None:
        backend = self._backend_combo.currentData()

        if backend == "openrouter":
            key = self._api_key_edit.text().strip()
            if not key:
                self._model_status.setText(
                    "Enter your API key above to load the full model list."
                )
                return
            url = BACKENDS["openrouter"]["url"]
        elif backend == "huggingface":
            key = self._api_key_edit.text().strip()
            url = BACKENDS["huggingface"]["url"]
        elif backend == "custom":
            url = self._custom_url_edit.text().strip() or self._settings.custom_url
            key = ""
        else:
            info = BACKENDS.get(backend, {})
            url = info.get("url", "")
            key = info.get("key", "")

        self._model_status.setText("Loading models…")
        self._model_combo.setEnabled(False)
        self._refresh_btn.setEnabled(False)

        self._fetcher = _ModelFetcher(url, key)
        self._fetcher.models_ready.connect(self._on_models_ready)
        self._fetcher.start()

    def _on_models_ready(self, models: list[str]) -> None:
        self._model_combo.setEnabled(True)
        self._refresh_btn.setEnabled(True)
        current = self._model_combo.currentText()

        if models:
            self._all_models = models
            self._apply_filter(self._search_edit.text(), preserve_selection=current)
            self._model_status.setText(f"{len(models)} model(s) available.")
        else:
            self._all_models = []
            self._model_status.setText("Could not load models — check key / connection.")

    # ── Search / filter ─────────────────────────────────────────────────────────

    def _filter_models(self, text: str) -> None:
        self._apply_filter(text, preserve_selection=self._model_combo.currentText())

    def _apply_filter(self, query: str, preserve_selection: str = "") -> None:
        q = query.strip().lower()
        if q and self._all_models:
            filtered = [m for m in self._all_models if q in m.lower()]
        else:
            filtered = self._all_models

        self._model_combo.clear()
        if filtered:
            self._model_combo.addItems(filtered)
            if preserve_selection in filtered:
                self._model_combo.setCurrentText(preserve_selection)
            else:
                self._model_combo.setCurrentIndex(0)
        elif q:
            # Nothing matched — show the typed query so user can still submit it
            self._model_combo.setCurrentText(preserve_selection)

        if self._all_models:
            shown = len(filtered) if filtered else 0
            total = len(self._all_models)
            suffix = f" (showing {shown}/{total})" if q else f" ({total} total)"
            self._model_status.setText(f"{total} model(s) available{suffix}.")

    # ── Misc ────────────────────────────────────────────────────────────────────

    def _clear_history(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Delete all conversation history? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from app.core.conversation import ConversationStore
            ConversationStore().clear_all()
            QMessageBox.information(self, "Done", "Conversation history cleared.")

    def accept(self) -> None:
        backend = self._backend_combo.currentData()
        self._settings.backend = backend

        if backend in ("openrouter", "huggingface"):
            key = self._api_key_edit.text().strip()
            self._settings.set_api_key(backend, key)

        if backend == "custom":
            self._settings.custom_url = self._custom_url_edit.text().strip()

        self._settings.model = self._model_combo.currentText().strip()
        self._settings.quality = QUALITY_KEYS[self._quality_combo.currentIndex()]
        self._settings.render_timeout = self._timeout_spin.value()

        super().accept()
