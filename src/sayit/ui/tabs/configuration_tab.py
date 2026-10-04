from typing import List, Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QKeySequenceEdit,
    QLabel,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core.asr.models.registry import (
    delete_asr_model,
    get_all_models_with_status,
    is_model_downloaded,
)
from ...core.audio import AudioRecorder
from ...core.context import PROFILE_DESCRIPTIONS, Profile
from ...core.context.profiles import AUTO
from ...core.settings import HotkeyConfig, Settings
from ..download_dialog import ModelDownloadThread


class ConfigurationTab(QWidget):

    reset_requested = Signal()

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        # Guard model/mode widget synchronization so UI mirroring never becomes
        # a second writer of the persistent model selection.
        self._syncing_model_selection = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        layout.addWidget(self._create_general_section())
        layout.addWidget(self._create_audio_section())
        layout.addWidget(self._create_hotkey_section())
        layout.addWidget(self._create_correction_section())
        layout.addWidget(self._create_context_section())
        layout.addWidget(self._create_intelligence_section())
        layout.addWidget(self._create_speech_mode_section())
        layout.addWidget(self._create_advanced_performance_section())
        layout.addWidget(self._create_domain_section())
        layout.addWidget(self._create_safe_zones_section())
        layout.addWidget(self._create_asr_model_section())

        layout.addStretch()

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

    def _create_general_section(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        startup_group = QGroupBox("Startup")
        startup_layout = QVBoxLayout(startup_group)

        self._start_minimized_cb = QCheckBox("Start minimized to tray")
        startup_layout.addWidget(self._start_minimized_cb)

        self._autostart_cb = QCheckBox("Start automatically on login")
        startup_layout.addWidget(self._autostart_cb)

        layout.addWidget(startup_group)
        return widget

    def _create_audio_section(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        audio_group = QGroupBox("Audio")
        audio_layout = QFormLayout(audio_group)

        device_layout = QHBoxLayout()
        self._device_combo = QComboBox()
        self._refresh_devices()
        device_layout.addWidget(self._device_combo, 1)

        refresh_btn = QPushButton("⟳")
        refresh_btn.setFixedWidth(30)
        refresh_btn.setToolTip("Refresh device list")
        refresh_btn.clicked.connect(self._refresh_devices)
        device_layout.addWidget(refresh_btn)

        audio_layout.addRow("Input Device:", device_layout)

        self._sample_rate_combo = QComboBox()
        self._sample_rate_combo.addItem("16000 Hz (Recommended)", 16000)
        self._sample_rate_combo.addItem("22050 Hz", 22050)
        self._sample_rate_combo.addItem("44100 Hz", 44100)
        audio_layout.addRow("Sample Rate:", self._sample_rate_combo)

        layout.addWidget(audio_group)
        return widget

    def _refresh_devices(self) -> None:
        current = (
            self._device_combo.currentData() if hasattr(self, "_device_combo") else None
        )
        self._device_combo.clear()
        self._device_combo.addItem("System Default", None)

        for device in AudioRecorder.list_devices():
            self._device_combo.addItem(device.name, device.name)

        if current:
            idx = self._device_combo.findData(current)
            if idx >= 0:
                self._device_combo.setCurrentIndex(idx)

    def _create_hotkey_section(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        hotkey_group = QGroupBox("Push-to-Talk Hotkey")
        hotkey_layout = QFormLayout(hotkey_group)

        self._hotkey_edit = QKeySequenceEdit()
        hotkey_layout.addRow("Hold to record:", self._hotkey_edit)

        instructions = QLabel(
            "Click the field above and press your desired key combination.\n"
            "The recording will start when you hold the keys and stop when you release."
        )
        instructions.setStyleSheet("color: gray; font-size: 11px;")
        instructions.setWordWrap(True)
        hotkey_layout.addRow("", instructions)

        layout.addWidget(hotkey_group)
        return widget

    def _create_correction_section(self) -> QWidget:
        """Local, on-device post-ASR correction toggles (Phase 6G).

        Both options run entirely locally with no network and no transcript
        logging. They are conservative by design and ON by default; this
        section lets the user turn them off.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Text Correction (on-device)")
        group_layout = QVBoxLayout(group)

        self._technical_correction_cb = QCheckBox(
            "Normalize common technical terms (e.g. \"git hub\" \u2192 GitHub)"
        )
        self._technical_correction_cb.setToolTip(
            "Deterministic, local normalization of registered developer terms "
            "and spelled-out acronyms. Does not use fuzzy matching, guess names, "
            "or contact any network."
        )
        self._technical_correction_cb.setAccessibleName(
            "Normalize common technical terms"
        )
        group_layout.addWidget(self._technical_correction_cb)

        self._structured_formatting_cb = QCheckBox(
            "Format structured values (versions, percentages, common dates)"
        )
        self._structured_formatting_cb.setToolTip(
            "Conservative local formatting of clearly structured values, e.g. "
            "\"three point two\" \u2192 3.2, \"ninety five percent\" \u2192 95%. "
            "Ordinary prose is left unchanged."
        )
        self._structured_formatting_cb.setAccessibleName(
            "Format structured values"
        )
        group_layout.addWidget(self._structured_formatting_cb)

        note = QLabel(
            "Runs locally on your computer. No network, no transcript logging."
        )
        note.setStyleSheet("color: gray; font-size: 11px;")
        note.setWordWrap(True)
        group_layout.addWidget(note)

        layout.addWidget(group)
        return widget

    def _create_context_section(self) -> QWidget:
        """Phase 8A: local context engine controls.

        Lets the user (a) toggle automatic context detection, (b) force a
        specific profile via a manual override that always wins over detection,
        and (c) see which profiles exist. All local; detection reads only active
        application/window metadata and never content.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Context & Profiles (on-device)")
        group_layout = QVBoxLayout(group)

        self._context_detection_cb = QCheckBox(
            "Detect the active application and pick a profile automatically"
        )
        self._context_detection_cb.setToolTip(
            "Reads only the active application/window name locally. No "
            "screenshots, no clipboard, no page or editor contents."
        )
        self._context_detection_cb.setAccessibleName(
            "Enable automatic context detection"
        )
        group_layout.addWidget(self._context_detection_cb)

        override_row = QHBoxLayout()
        override_label = QLabel("Mode override:")
        self._context_override_combo = QComboBox()
        self._context_override_combo.setAccessibleName("Context mode override")
        # "Auto" first, then each concrete profile. Data holds the stored token.
        self._context_override_combo.addItem("Auto", AUTO)
        for prof in Profile:
            self._context_override_combo.addItem(prof.label, prof.value)
        self._context_override_combo.currentIndexChanged.connect(
            self._on_override_changed
        )
        override_row.addWidget(override_label)
        override_row.addWidget(self._context_override_combo, 1)
        group_layout.addLayout(override_row)

        self._context_profile_desc = QLabel("")
        self._context_profile_desc.setWordWrap(True)
        self._context_profile_desc.setStyleSheet("color: gray; font-size: 11px;")
        group_layout.addWidget(self._context_profile_desc)

        note = QLabel(
            "A manual override always wins over automatic detection. Profiles "
            "only adjust the on-device correction above; they never rewrite your "
            "words. Runs locally \u2014 no network."
        )
        note.setStyleSheet("color: gray; font-size: 11px;")
        note.setWordWrap(True)
        group_layout.addWidget(note)

        layout.addWidget(group)
        return widget

    def _on_override_changed(self, index: int) -> None:
        token = self._context_override_combo.currentData()
        if token and token != AUTO:
            prof = Profile.from_value(token)
            self._context_profile_desc.setText(PROFILE_DESCRIPTIONS.get(prof, ""))
        else:
            self._context_profile_desc.setText(
                "Automatic: the profile follows the active application."
            )


    def _create_intelligence_section(self) -> QWidget:
        """Phase 8B-8G feature toggles (local intelligence layer)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Local Intelligence (on-device)")
        group_layout = QVBoxLayout(group)

        self._intelligence_cb = QCheckBox(
            "Enable local intelligence (voice edit, snippets, structure, developer)"
        )
        self._intelligence_cb.setAccessibleName("Enable local intelligence")
        self._intelligence_cb.setToolTip(
            "Master switch. When off, SayIt behaves as plain dictation plus the "
            "existing on-device correction. All features run locally."
        )
        group_layout.addWidget(self._intelligence_cb)

        self._voice_edit_cb = QCheckBox("Voice edit / backtrack commands")
        self._voice_edit_cb.setAccessibleName("Enable voice edit")
        group_layout.addWidget(self._voice_edit_cb)

        self._snippets_cb = QCheckBox("Snippets (spoken trigger \u2192 saved text)")
        self._snippets_cb.setAccessibleName("Enable snippets")
        group_layout.addWidget(self._snippets_cb)

        self._structure_cb = QCheckBox("Structure commands (new line, lists, \u2026)")
        self._structure_cb.setAccessibleName("Enable structure commands")
        group_layout.addWidget(self._structure_cb)

        self._developer_mode_cb = QCheckBox(
            "Developer mode (explicit casing, code block)"
        )
        self._developer_mode_cb.setAccessibleName("Enable developer mode")
        group_layout.addWidget(self._developer_mode_cb)

        note = QLabel(
            "These never execute commands or code \u2014 all output is inserted "
            "as text. Deterministic and explainable."
        )
        note.setStyleSheet("color: gray; font-size: 11px;")
        note.setWordWrap(True)
        group_layout.addWidget(note)

        layout.addWidget(group)
        return widget

    def _create_speech_mode_section(self) -> QWidget:
        """Speech Mode selector: Fast (Parakeet, default) vs Higher Accuracy
        (Whisper Small, opt-in). Maps to settings.model_id via the speech_mode
        module; NOT coupled to the experimental intelligence flag. Reuses the
        existing model download infrastructure for the optional model."""
        from ...core.asr import speech_mode as SM
        from PySide6.QtWidgets import QRadioButton, QButtonGroup

        self._SM = SM
        widget = QWidget()
        layout = QVBoxLayout(widget)
        group = QGroupBox("Speech Mode")
        group_layout = QVBoxLayout(group)

        self._mode_group = QButtonGroup(self)
        self._mode_radios = {}
        self._mode_status_labels = {}
        for m in SM.all_modes():
            row = QWidget()
            row_l = QVBoxLayout(row)
            row_l.setContentsMargins(0, 0, 0, 6)
            rb = QRadioButton(f"{m.label} \u2014 {m.tagline}")
            rb.setAccessibleName(f"Speech mode {m.label}")
            rb.setProperty("mode", m.mode)
            rb.toggled.connect(self._on_mode_radio_toggled)
            self._mode_group.addButton(rb)
            self._mode_radios[m.mode] = rb
            row_l.addWidget(rb)

            status = QLabel("")
            status.setStyleSheet("color: gray; font-size: 11px;")
            status.setWordWrap(True)
            self._mode_status_labels[m.mode] = status
            row_l.addWidget(status)

            if m.optional:
                dl = QPushButton("Download")
                dl.setAccessibleName(f"Download {m.label} model")
                dl.setProperty("mode", m.mode)
                dl.clicked.connect(lambda _=False, mm=m.mode: self._on_download_mode(mm))
                self._mode_download_btn = dl
                row_l.addWidget(dl)
            group_layout.addWidget(row)

        note = QLabel(
            "Fast is the default. Higher Accuracy uses a larger local model with "
            "stronger technical-term recognition in SayIt's measured evaluation, "
            "but is slower. Both run fully on-device."
        )
        note.setStyleSheet("color: gray; font-size: 11px;")
        note.setWordWrap(True)
        group_layout.addWidget(note)

        layout.addWidget(group)
        self._refresh_mode_status()
        return widget

    def _refresh_mode_status(self) -> None:
        SM = self._SM
        for mode, lbl in self._mode_status_labels.items():
            lbl.setText(self._SM.mode_status(mode))
        # Download button only enabled when the optional model is missing.
        btn = getattr(self, "_mode_download_btn", None)
        if btn is not None:
            btn.setVisible(not SM.is_mode_available(SM.HIGHER_ACCURACY))

    def _on_download_mode(self, mode: str) -> None:
        # Reuse the existing ASR model download flow for the optional model.
        model_id = self._SM.model_id_for_mode(mode)
        self._load_model_selection(model_id)  # select in the model combo
        self._on_download_clicked()

    def _create_advanced_performance_section(self) -> QWidget:
        """Advanced / Performance: optional Whisper Small CPU thread count.

        Whisper-only (does NOT affect Parakeet, the production default). Bounded,
        explicit choices {Default/4, 6, 8}; persisted to
        ``settings.whisper_small_cpu_threads``. NOT coupled to the experimental
        intelligence flag. Deliberately non-promissory about any speedup.
        """
        from PySide6.QtWidgets import QRadioButton, QButtonGroup

        from ...core.settings.settings import (
            WHISPER_CPU_THREAD_CHOICES,
            DEFAULT_WHISPER_CPU_THREADS,
        )

        widget = QWidget()
        layout = QVBoxLayout(widget)
        group = QGroupBox("Advanced \u00b7 Performance")
        group_layout = QVBoxLayout(group)

        heading = QLabel("Whisper Small CPU threads")
        heading.setStyleSheet("font-weight: 600;")
        group_layout.addWidget(heading)

        self._whisper_threads_group = QButtonGroup(self)
        self._whisper_threads_radios = {}
        for value in WHISPER_CPU_THREAD_CHOICES:
            label = "Default (4)" if value == DEFAULT_WHISPER_CPU_THREADS else str(value)
            rb = QRadioButton(label)
            rb.setAccessibleName(f"Whisper Small CPU threads {label}")
            rb.setProperty("threads", value)
            self._whisper_threads_group.addButton(rb)
            self._whisper_threads_radios[value] = rb
            group_layout.addWidget(rb)

        desc = QLabel(
            "Higher values may reduce transcription time on some CPUs, but may "
            "increase CPU usage. This affects the Higher Accuracy (Whisper Small) "
            "mode only; the Fast (Parakeet) default is unchanged."
        )
        desc.setStyleSheet("color: gray; font-size: 11px;")
        desc.setWordWrap(True)
        group_layout.addWidget(desc)

        layout.addWidget(group)
        return widget

    # Human-friendly labels for the user-facing technical domains.
    _DOMAIN_LABELS = {
        "web": "Web Development",
        "python": "Python",
        "ai_ml": "AI / ML",
        "data_sql": "Data / SQL",
        "devops_cloud": "DevOps / Cloud",
        "cybersecurity": "Cybersecurity",
        "academic": "Academic / Research",
        "aerospace": "Aerospace / Engineering",
        "control_systems": "Control Systems",
        "chemistry": "Chemistry / Biochemistry",
        "electronics": "Electronics",
        "mathematics": "Mathematics / Scientific Computing",
    }

    def _create_domain_section(self) -> QWidget:
        """Opt-in technical domain selector (domain-coverage expansion).

        A user chooses DOMAINS, not dictionary entries. Enabling a domain only
        raises a bounded prior in ranking; it never forces a correction and
        never learns from speech. Effective only when local intelligence is on.
        """
        from ...core.knowledge.domain_activation import all_domain_names

        widget = QWidget()
        layout = QVBoxLayout(widget)
        group = QGroupBox("Technical Domains (opt-in)")
        group_layout = QVBoxLayout(group)

        intro = QLabel(
            "Choose the technical domains you work in. SayIt will prioritize "
            "relevant terminology for recognition. This is a prior, not a forced "
            "correction \u2014 ordinary words stay ordinary, and nothing is learned "
            "from your speech."
        )
        intro.setStyleSheet("color: gray; font-size: 11px;")
        intro.setWordWrap(True)
        group_layout.addWidget(intro)

        self._domain_search = QComboBox()
        self._domain_search.setEditable(True)
        self._domain_search.setPlaceholderText("Search domains\u2026")
        self._domain_search.setAccessibleName("Search technical domains")
        self._domain_search.lineEdit().textChanged.connect(self._filter_domains)
        group_layout.addWidget(self._domain_search)

        self._domain_checks = {}
        for name in all_domain_names():
            cb = QCheckBox(self._DOMAIN_LABELS.get(name, name))
            cb.setAccessibleName(f"Enable domain {name}")
            self._domain_checks[name] = cb
            group_layout.addWidget(cb)

        reset_btn = QPushButton("Reset domains to defaults")
        reset_btn.setAccessibleName("Reset technical domains to defaults")
        reset_btn.clicked.connect(self._reset_domains)
        group_layout.addWidget(reset_btn)

        layout.addWidget(group)
        return widget

    def _filter_domains(self, text: str) -> None:
        text = (text or "").strip().lower()
        for name, cb in self._domain_checks.items():
            label = self._DOMAIN_LABELS.get(name, name).lower()
            cb.setVisible(text in label or text in name or not text)

    def _reset_domains(self) -> None:
        # Default: nothing explicitly enabled (conservative; context-suggested
        # developer domains apply automatically when intelligence is on).
        for cb in self._domain_checks.values():
            cb.setChecked(False)

    def _create_safe_zones_section(self) -> QWidget:
        """Phase 8E Safe Zones: protected applications where recording is
        blocked. Reuses 8A local app detection; reads only app/window metadata."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Safe Zones (protected applications)")
        group_layout = QVBoxLayout(group)

        self._safe_zones_cb = QCheckBox(
            "Block recording while a protected application is in the foreground"
        )
        self._safe_zones_cb.setAccessibleName("Enable safe zones")
        group_layout.addWidget(self._safe_zones_cb)

        self._protected_list = QListWidget()
        self._protected_list.setAccessibleName("Protected applications")
        self._protected_list.setFixedHeight(96)
        group_layout.addWidget(self._protected_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add\u2026")
        add_btn.setAccessibleName("Add protected application")
        add_btn.clicked.connect(self._on_add_protected)
        btn_row.addWidget(add_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setAccessibleName("Remove protected application")
        remove_btn.clicked.connect(self._on_remove_protected)
        btn_row.addWidget(remove_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setAccessibleName("Clear protected applications")
        clear_btn.clicked.connect(lambda: self._protected_list.clear())
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        group_layout.addLayout(btn_row)

        note = QLabel(
            "Enter part of an application name (e.g. \"keepass\", \"1password\", "
            "\"bank\"). Matched against the foreground app/window locally. No "
            "screenshots, clipboard, or page contents are read; no audio is "
            "recorded while a protected app is active."
        )
        note.setStyleSheet("color: gray; font-size: 11px;")
        note.setWordWrap(True)
        group_layout.addWidget(note)

        layout.addWidget(group)
        return widget

    def _on_add_protected(self) -> None:
        text, ok = QInputDialog.getText(
            self, "Add protected application", "Application name contains:"
        )
        if ok and text.strip():
            self._protected_list.addItem(text.strip())

    def _on_remove_protected(self) -> None:
        for item in self._protected_list.selectedItems():
            self._protected_list.takeItem(self._protected_list.row(item))


    def _create_asr_model_section(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        model_group = QGroupBox("ASR Model")
        model_layout = QFormLayout(model_group)

        model_row_layout = QHBoxLayout()
        self._model_combo = QComboBox()
        self._model_combo.setStyleSheet("font-family: monospace;")
        model_row_layout.addWidget(self._model_combo, 1)

        self._download_btn = QPushButton("Download")
        self._download_btn.setFixedWidth(80)
        self._download_btn.setToolTip("Download selected model")
        self._download_btn.clicked.connect(self._on_download_clicked)
        model_row_layout.addWidget(self._download_btn)

        self._delete_model_btn = QPushButton("🗑")
        self._delete_model_btn.setFixedWidth(30)
        self._delete_model_btn.setToolTip("Delete selected model from cache")
        self._delete_model_btn.clicked.connect(self._on_delete_model_clicked)
        model_row_layout.addWidget(self._delete_model_btn)

        self._refresh_model_list()
        self._model_combo.currentIndexChanged.connect(self._on_model_combo_changed)

        model_layout.addRow("Model:", model_row_layout)

        self._download_progress = QProgressBar()
        self._download_progress.setRange(0, 100)
        self._download_progress.hide()
        model_layout.addRow("", self._download_progress)

        self._cancel_download_btn = QPushButton("Cancel")
        self._cancel_download_btn.hide()
        self._cancel_download_btn.clicked.connect(self._on_cancel_download)
        model_layout.addRow("", self._cancel_download_btn)

        layout.addWidget(model_group)

        self._download_thread: Optional[ModelDownloadThread] = None

        reset_btn = QPushButton("Reset All Settings to Defaults")
        reset_btn.clicked.connect(self.reset_requested.emit)
        layout.addWidget(reset_btn)
        return widget

    def _refresh_model_list(self) -> None:
        current_data = (
            self._model_combo.currentData() if self._model_combo.count() > 0 else None
        )
        self._model_combo.clear()

        for model, status in get_all_models_with_status():
            indicator = "✓" if status == "downloaded" else "↓"
            display_text = f"{model.name}  {indicator}"
            self._model_combo.addItem(display_text, model.id)

        if current_data:
            idx = self._model_combo.findData(current_data)
            if idx >= 0:
                self._model_combo.setCurrentIndex(idx)

        self._update_button_states()

    def refresh_model_list(self) -> None:
        self._refresh_model_list()

    def _update_button_states(self) -> None:
        current_data = self._model_combo.currentData()
        is_active_model = current_data == self._settings.model_id
        downloaded = is_model_downloaded(current_data) if current_data else True

        self._delete_model_btn.setEnabled(not is_active_model and downloaded)
        if is_active_model:
            self._delete_model_btn.setToolTip("Cannot delete currently active model")
        else:
            self._delete_model_btn.setToolTip("Delete selected model from cache")

        self._download_btn.setEnabled(not downloaded)

    def _on_model_combo_changed(self, index: int) -> None:
        self._update_button_states()
        if not self._syncing_model_selection and hasattr(self, "_SM"):
            self._sync_mode_radios_from_model(self._get_selected_model_name())

    def _on_mode_radio_toggled(self, checked: bool) -> None:
        """Mirror a product speech mode into the concrete ASR model selection."""
        if not checked or self._syncing_model_selection or not hasattr(self, "_model_combo"):
            return

        sender = self.sender()
        mode = sender.property("mode") if sender is not None else None
        if not mode:
            return

        if not self._SM.is_mode_available(mode):
            self._syncing_model_selection = True
            try:
                self._sync_mode_radios_from_model(self._model_combo.currentData())
            finally:
                self._syncing_model_selection = False
            QMessageBox.warning(
                self,
                "Model not installed",
                f"{self._SM.get_mode(mode).label} is not installed yet. "
                "Download it first, then select it.",
            )
            return

        self._syncing_model_selection = True
        try:
            self._load_model_selection(self._SM.model_id_for_mode(mode))
        finally:
            self._syncing_model_selection = False

    def _sync_mode_radios_from_model(self, model_id: Optional[str]) -> None:
        """Reflect the concrete combo model without ever overwriting it."""
        if not hasattr(self, "_mode_radios"):
            return

        mode = None
        if self._SM.is_known_mode_model(model_id):
            mode = self._SM.mode_for_model_id(model_id)

        self._syncing_model_selection = True
        try:
            self._mode_group.setExclusive(mode is not None)
            if mode is None:
                self._mode_group.setExclusive(False)
                for rb in self._mode_radios.values():
                    rb.setChecked(False)
                self._mode_group.setExclusive(True)
            else:
                for candidate, rb in self._mode_radios.items():
                    rb.setChecked(candidate == mode)
        finally:
            self._syncing_model_selection = False

    def _on_download_clicked(self) -> None:
        model_id = self._model_combo.currentData()
        if not model_id:
            return

        self._download_progress.setValue(0)
        self._download_progress.show()
        self._cancel_download_btn.show()
        self._download_btn.setEnabled(False)
        self._model_combo.setEnabled(False)

        self._download_thread = ModelDownloadThread(model_id)
        self._download_thread.progress.connect(self._on_download_progress)
        self._download_thread.status_changed.connect(self._on_download_status)
        self._download_thread.finished.connect(self._on_download_finished)
        self._download_thread.error.connect(self._on_download_error)
        self._download_thread.start()

    def _on_download_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            percent = int((downloaded / total) * 100)
            self._download_progress.setValue(percent)
            self._download_progress.setFormat(f"{percent}%")

    def _on_download_status(self, status: str) -> None:
        self._download_progress.setFormat(status)

    def _on_download_finished(self, success: bool) -> None:
        self._download_progress.hide()
        self._cancel_download_btn.hide()
        self._model_combo.setEnabled(True)
        self._download_thread = None

        if success:
            self._refresh_model_list()
            QMessageBox.information(
                self, "Download Complete", "Model downloaded successfully!"
            )
        self._update_button_states()

    def _on_download_error(self, error_msg: str) -> None:
        QMessageBox.warning(
            self, "Download Failed", f"Failed to download model:\n{error_msg}"
        )

    def _on_cancel_download(self) -> None:
        if self._download_thread:
            self._download_thread.cancel()
            self._cancel_download_btn.setEnabled(False)
            self._cancel_download_btn.setText("Cancelling...")

    def _update_delete_button_state(self) -> None:
        self._update_button_states()

    def _on_delete_model_clicked(self) -> None:
        model_name = self._model_combo.currentData()
        if not model_name:
            return

        reply = QMessageBox.question(
            self,
            "Delete Model",
            f"Are you sure you want to delete '{model_name}' from the cache?\n\n"
            "This will free up disk space but the model will need to be\n"
            "re-downloaded if you want to use it again.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        success, message = delete_asr_model(model_name)

        if success:
            QMessageBox.information(self, "Model Deleted", message)
            self._refresh_model_list()
        else:
            QMessageBox.warning(self, "Deletion Failed", message)

    def _load_model_selection(self, model_name: str) -> None:
        idx = self._model_combo.findData(model_name)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)

    def _get_selected_model_name(self) -> str:
        return self._model_combo.currentData() or ""

    def load_settings(self) -> None:

        self._start_minimized_cb.setChecked(self._settings.start_minimized)
        self._autostart_cb.setChecked(self._settings.auto_start_on_login)

        self._technical_correction_cb.setChecked(
            self._settings.technical_correction_enabled
        )
        self._structured_formatting_cb.setChecked(
            self._settings.structured_formatting_enabled
        )

        # Phase 8A context controls.
        self._context_detection_cb.setChecked(
            self._settings.context_detection_enabled
        )
        override_token = self._settings.context_override or AUTO
        idx = self._context_override_combo.findData(override_token)
        if idx < 0:
            idx = self._context_override_combo.findData(AUTO)
        self._context_override_combo.setCurrentIndex(max(idx, 0))
        self._on_override_changed(self._context_override_combo.currentIndex())

        # Phase 8B-8G intelligence toggles.
        self._intelligence_cb.setChecked(self._settings.intelligence_enabled)
        self._voice_edit_cb.setChecked(self._settings.voice_edit_enabled)
        self._snippets_cb.setChecked(self._settings.snippets_enabled)
        self._structure_cb.setChecked(self._settings.structure_enabled)
        self._developer_mode_cb.setChecked(self._settings.developer_mode_enabled)

        # Domain-coverage selector: check the user's explicitly-enabled domains.
        enabled = set(getattr(self._settings, "enabled_domains", []) or [])
        for name, cb in getattr(self, "_domain_checks", {}).items():
            cb.setChecked(name in enabled)

        # Speech Mode mirrors the persisted concrete model; it never writes it.
        if hasattr(self, "_mode_radios"):
            self._sync_mode_radios_from_model(self._settings.model_id)
            self._refresh_mode_status()

        # Advanced / Performance: Whisper Small CPU threads (bounded {4,6,8}).
        if hasattr(self, "_whisper_threads_radios"):
            from ...core.settings.settings import DEFAULT_WHISPER_CPU_THREADS
            val = self._settings.whisper_small_cpu_threads
            rb = self._whisper_threads_radios.get(val) or \
                self._whisper_threads_radios.get(DEFAULT_WHISPER_CPU_THREADS)
            if rb is not None:
                rb.setChecked(True)

        # Phase 8E safe zones.
        self._safe_zones_cb.setChecked(self._settings.safe_zones_enabled)
        self._protected_list.clear()
        for entry in self._settings.protected_apps:
            if entry and entry.strip():
                self._protected_list.addItem(entry.strip())

        self._load_model_selection(self._settings.model_id)

        hotkey = self._settings.hotkey
        key_sequence = "+".join(hotkey.modifiers + [hotkey.key])
        self._hotkey_edit.setKeySequence(QKeySequence(key_sequence))

        idx = self._sample_rate_combo.findData(self._settings.sample_rate)
        if idx >= 0:
            self._sample_rate_combo.setCurrentIndex(idx)

        if self._settings.input_device:
            idx = self._device_combo.findData(self._settings.input_device)
            if idx >= 0:
                self._device_combo.setCurrentIndex(idx)

    def save_settings(self) -> bool:
        model_name = self._get_selected_model_name()
        if model_name and model_name != self._settings.model_id:
            if not self._validate_model_name(model_name):
                return False

        self._settings.start_minimized = self._start_minimized_cb.isChecked()
        self._settings.auto_start_on_login = self._autostart_cb.isChecked()

        self._settings.technical_correction_enabled = (
            self._technical_correction_cb.isChecked()
        )
        self._settings.structured_formatting_enabled = (
            self._structured_formatting_cb.isChecked()
        )

        # Phase 8A context controls.
        self._settings.context_detection_enabled = (
            self._context_detection_cb.isChecked()
        )
        self._settings.context_override = (
            self._context_override_combo.currentData() or AUTO
        )

        # Phase 8B-8G intelligence toggles.
        self._settings.intelligence_enabled = self._intelligence_cb.isChecked()
        self._settings.voice_edit_enabled = self._voice_edit_cb.isChecked()
        self._settings.snippets_enabled = self._snippets_cb.isChecked()
        self._settings.structure_enabled = self._structure_cb.isChecked()
        self._settings.developer_mode_enabled = self._developer_mode_cb.isChecked()

        # Domain-coverage selector -> explicit enabled domains.
        self._settings.enabled_domains = [
            name for name, cb in getattr(self, "_domain_checks", {}).items()
            if cb.isChecked()
        ]

        # Phase 8E safe zones.
        self._settings.safe_zones_enabled = self._safe_zones_cb.isChecked()
        self._settings.protected_apps = [
            self._protected_list.item(i).text().strip()
            for i in range(self._protected_list.count())
            if self._protected_list.item(i).text().strip()
        ]

        self._settings.sample_rate = self._sample_rate_combo.currentData()
        self._settings.input_device = self._device_combo.currentData()

        # The ASR Model combo is the single persistent source of truth.
        # Speech Mode radios only mirror/select that combo.
        if model_name:
            self._settings.model_id = model_name

        # Advanced / Performance: persist the selected Whisper Small thread
        # count (Whisper-only; does not affect Parakeet). Validator/loader
        # enforce the bounded {4,6,8} set; default 4.
        if hasattr(self, "_whisper_threads_group"):
            checked = self._whisper_threads_group.checkedButton()
            if checked is not None:
                self._settings.whisper_small_cpu_threads = int(
                    checked.property("threads")
                )

        hotkey_config = self._parse_key_sequence()
        if hotkey_config:
            self._settings.hotkey = hotkey_config

        return True

    def _validate_model_name(self, model_name: str) -> bool:
        if not model_name or len(model_name) < 3:
            QMessageBox.warning(
                self,
                "Invalid Model Name",
                "Please enter a valid model name.",
            )
            return False

        return True

    def _parse_key_sequence(self) -> Optional[HotkeyConfig]:
        key_sequence = self._hotkey_edit.keySequence()
        if key_sequence.isEmpty():
            return None

        seq_str = key_sequence.toString()
        if not seq_str:
            return None

        parts = seq_str.split("+")
        if not parts:
            return None

        modifiers: List[str] = []
        key = parts[-1].lower()

        for part in parts[:-1]:
            mod = part.strip().lower()
            if mod in ("ctrl", "control", "⌃"):
                modifiers.append("ctrl")
            elif mod in ("alt", "option", "⌥"):
                modifiers.append("alt")
            elif mod in ("shift", "⇧"):
                modifiers.append("shift")
            elif mod in ("meta", "cmd", "command", "win", "⌘"):
                modifiers.append("cmd")

        # QKeySequence can stringify differently across Qt/platform versions.
        # Never allow an unrecognized modifier to propagate as an invalid
        # HotkeyConfig; fall back to the same safe default used by setup.
        if not modifiers:
            return HotkeyConfig()

        return HotkeyConfig(modifiers=list(dict.fromkeys(modifiers)), key=key.strip())
