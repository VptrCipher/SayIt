import os
from pathlib import Path
import signal
import sys
from datetime import datetime
from enum import Enum, auto
from functools import partial
from typing import Optional

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication

from . import __app_name__, __display_name__, __version__
from .core.asr import (
    EngineState,
    ModelLoaderThread,
    TranscriptionEngine,
    TranscriptionWorkerThread,
)
from .core.asr.pipeline_timing import PipelineTiming
from .core.asr.intelligence_pipeline import IntelligencePipeline
from .core.audio import AudioRecorder
from .core.context import ContextEngine
from .core.input import HotkeyListener
from .core.intelligence import IntelligenceOrchestrator, OrchestratorConfig
from .core.safezones import is_protected
from .core.snippets import snippets_from_any
from .core.voice_commands import OutputBuffer
from .core.output import TextOutputController
from .core.settings import (
    TranscriptionRecord,
    add_history_record,
    get_settings,
)
from .core.transcript_processor import LLMProcessor
from .ui.download_dialog import DownloadDialog
from .ui.main_window import SettingsWindow
from .ui.recording_toast import RecordingToast
from .ui.setup_wizard import SetupWizard
from .ui.tray import SystemTray, TrayStatus
from .utils.logger import get_logger
from .utils.platform import set_autostart

logger = get_logger(__name__)

# Pattern to detect unknown/garbled tokens from the transcription model
_UNK_TOKEN_PATTERN = "<unk>"


class AppState(Enum):
    """Explicit runtime state of the dictation workflow.

    This is the single source of truth for "what is the app doing right now".
    Tray status is derived from it via a central mapping so the visible status
    can never drift from the real state. Legal transitions are enforced in
    _set_state's callers; every active state has a guaranteed exit to IDLE or
    ERROR.

    Transition map:
        IDLE        -> RECORDING (hotkey press) | SHUTTING_DOWN
        RECORDING   -> TRANSCRIBING (release w/ audio) | IDLE (no audio)
                       | CANCELLED (Esc) | ERROR (recorder failure)
                       | SHUTTING_DOWN
        TRANSCRIBING-> IDLE (success) | ERROR (failure)
                       | CANCELLED (Esc, result discarded) | SHUTTING_DOWN
        ERROR       -> IDLE (next action) | RECORDING | SHUTTING_DOWN
        CANCELLED   -> IDLE (transient; collapses immediately)
        SHUTTING_DOWN -> (terminal; no new work)
    """

    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    CANCELLED = auto()
    ERROR = auto()
    SHUTTING_DOWN = auto()


class TranscribeApp(QObject):

    def __init__(self):
        super().__init__()

        self._settings = get_settings()
        self._settings_window: Optional[SettingsWindow] = None

        self._tray = SystemTray()
        self._recording_toast = RecordingToast(__display_name__)
        self._latest_audio_level = 0.0
        self._latest_audio_spectrum: list[float] = []
        self._audio_level_timer = QTimer(self)
        self._audio_level_timer.setInterval(50)
        self._audio_level_timer.timeout.connect(self._update_audio_level)
        self._recorder = AudioRecorder(
            sample_rate=self._settings.sample_rate,
            device=self._settings.input_device,
            on_audio_level=self._capture_audio_level,
            on_audio_spectrum=self._capture_audio_spectrum,
        )
        self._transcriber = TranscriptionEngine(
            model_name=self._settings.model_id,
            on_state_change=self._on_engine_state_change,
            on_download_progress=self._on_download_progress,
            whisper_num_threads=self._settings.whisper_small_cpu_threads,
        )
        self._hotkey_listener = HotkeyListener()
        self._text_output = TextOutputController()
        self._download_dialog: Optional[DownloadDialog] = None
        self._model_loader_thread: Optional[ModelLoaderThread] = None
        self._transcription_worker: Optional[TranscriptionWorkerThread] = None
        # Monotonic id identifying the dictation job that currently owns text
        # output. Each started transcription increments the counter; completion
        # signals that do not match the active id are stale and are discarded so
        # an older job can never insert into a newer context.
        self._job_counter = 0
        self._active_job_id: Optional[int] = None

        # Single source of truth for the dictation workflow state. Tray status
        # is always derived from this via _set_state so the two cannot diverge.
        self._state: AppState = AppState.IDLE

        # Transient, in-memory copy of the most recent transcript. This exists
        # so a failed insertion is always recoverable even when persistent
        # history is disabled. It is NOT written to disk.
        self._last_transcript: Optional[str] = None

        # Lightweight pipeline timing (developer diagnostics only; never shown
        # in the UI). perf_counter timestamps for the active dictation.
        self._recording_started_at: Optional[float] = None
        self._transcribe_started_at: Optional[float] = None
        # Phase 6H: privacy-safe per-job pipeline timing (no transcript text).
        self._timing: Optional[PipelineTiming] = None

        # Startup model-load fallback tracking. A failed startup/default load
        # falls back once to a known-compatible model; an explicit user model
        # selection that fails is NOT silently replaced.
        self._loading_model_id: Optional[str] = None
        self._load_user_initiated = False
        self._fallback_attempted = False

        self._llm_processor: Optional[LLMProcessor] = None
        self._init_llm_processor()

        # Phase 8A: local context engine. Reads only active-window metadata and
        # resolves a formatting profile. Reads its config lazily from settings
        # so a settings change takes effect without re-wiring. Observe-only with
        # respect to the state machine: it never gates recording.
        self._context_engine = ContextEngine(self._settings)
        self._last_context = None

        # Phase 8H: intelligence orchestrator + bounded recent-output buffer for
        # voice editing. The orchestrator is pure/deterministic; the buffer is
        # in-memory only (never written to disk) and holds just the most recent
        # output unit so "scratch that" / "replace X with Y" have a safe target.
        self._orchestrator = IntelligenceOrchestrator(self._build_orchestrator_config())
        self._output_buffer = OutputBuffer()
        # Phase 9K: lazily-built experimental post-ASR intelligence pipeline.
        # Only constructed when the off-by-default flag is enabled; otherwise
        # the worker receives None and behaves exactly as before.
        self._post_asr_pipeline: Optional[IntelligencePipeline] = None

        self._tray.settings_requested.connect(self._show_settings)
        self._tray.quit_requested.connect(self._quit)
        self._hotkey_listener.hotkey_pressed.connect(self._start_recording)
        self._hotkey_listener.hotkey_released.connect(self._stop_recording)
        self._hotkey_listener.cancel_requested.connect(self._cancel_current)

    # Central mapping from workflow state to the visible tray status. CANCELLED
    # reuses the IDLE indicator (it collapses to IDLE immediately after a brief
    # log/message). LOADING is driven separately by engine state changes.
    _STATE_TO_TRAY = {
        AppState.IDLE: TrayStatus.IDLE,
        AppState.RECORDING: TrayStatus.RECORDING,
        AppState.TRANSCRIBING: TrayStatus.PROCESSING,
        AppState.CANCELLED: TrayStatus.IDLE,
        AppState.ERROR: TrayStatus.ERROR,
    }

    def _set_state(self, state: "AppState", message: str = "") -> None:
        """Set the workflow state and keep the tray status in sync.

        This is the only place that should drive tray status for the dictation
        workflow, so the visible status can never contradict the real state.
        Once SHUTTING_DOWN is entered, no further state change (and no tray
        reactivation) is permitted.
        """
        if self._state == AppState.SHUTTING_DOWN:
            logger.debug(f"Ignoring state change to {state} during shutdown")
            return

        self._state = state

        if state == AppState.SHUTTING_DOWN:
            return

        tray_status = self._STATE_TO_TRAY.get(state, TrayStatus.IDLE)
        self._tray.set_status(tray_status, message)

        # Mirror the workflow state onto the (optional) Home tab for secondary
        # visibility. This is observe-only: it never drives recording,
        # transcription, cancellation, or insertion.
        self._update_home(state)

    # Workflow state -> HomeState. ERROR falls back to IDLE because the Home tab
    # has no dedicated error presentation (the tray already surfaces errors).
    _STATE_TO_HOME = {
        AppState.IDLE: "IDLE",
        AppState.RECORDING: "LISTENING",
        AppState.TRANSCRIBING: "TRANSCRIBING",
        AppState.CANCELLED: "IDLE",
        AppState.ERROR: "IDLE",
    }

    def _update_home(self, state: "AppState", transcript: Optional[str] = None) -> None:
        """Reflect the given workflow state on the Home tab, if it exists.

        Guarded so it is a no-op when the settings window has not been created
        or is being torn down. Failures here must never affect the dictation
        workflow.
        """
        if state == AppState.SHUTTING_DOWN:
            return
        window = self._settings_window
        if window is None:
            return
        home = getattr(window, "home_tab", None)
        if home is None:
            return
        try:
            from .ui.tabs import HomeState

            if transcript is not None:
                home.set_state(HomeState.COMPLETE, transcript=transcript)
            else:
                home.set_state(HomeState[self._STATE_TO_HOME.get(state, "IDLE")])
        except Exception as e:
            logger.debug(f"Home state update skipped: {e}")

    def _get_post_asr_pipeline(self):
        """Return the experimental post-ASR intelligence pipeline when the
        off-by-default flag is enabled, else None (byte-identical behavior).

        Built lazily and cached. Fail-safe: construction failures yield None so
        dictation never breaks. Disabling the flag at runtime returns None
        immediately (rollback).
        """
        if not getattr(self._settings, "intelligence_experimental_enabled", False):
            return None
        if self._post_asr_pipeline is None:
            try:
                self._post_asr_pipeline = IntelligencePipeline(
                    threshold=getattr(self._settings, "intelligence_threshold", 0.90),
                    user_vocabulary=self._settings.custom_vocabulary,
                    domain_aware=getattr(self._settings, "intelligence_domain_aware", False),
                    enabled_domains=getattr(self._settings, "enabled_domains", None),
                    disabled_domains=getattr(self._settings, "disabled_domains", None),
                )
            except Exception as e:
                logger.debug(f"Post-ASR pipeline unavailable (safe): {e}")
                return None
        return self._post_asr_pipeline

    def _update_home_context(self, resolution) -> None:
        """Reflect the resolved context on the Home tab, if it exists.

        Observe-only and fully guarded: a failure here must never affect the
        dictation workflow. Shows a short display string such as 'Developer' or
        'Auto · VS Code'.
        """
        window = self._settings_window
        if window is None:
            return
        home = getattr(window, "home_tab", None)
        if home is None:
            return
        setter = getattr(home, "set_context", None)
        if setter is None:
            return
        try:
            setter(resolution.display())
        except Exception as e:
            logger.debug(f"Home context update skipped: {e}")

    def _update_home_speech_mode(self) -> None:
        """Show the subtle current speech-mode status on Home."""
        window = self._settings_window
        if window is None:
            return
        home = getattr(window, "home_tab", None)
        setter = getattr(home, "set_speech_mode", None)
        if setter is None:
            return
        try:
            from .core.asr import speech_mode as SM
            setter(SM.status_line(self._settings.model_id))
        except Exception as e:
            logger.debug(f"Home speech-mode update skipped: {e}")

    def _build_orchestrator_config(self) -> "OrchestratorConfig":
        """Build the orchestrator feature-config from current settings.

        A disabled master switch (``intelligence_enabled``) disables every
        feature so the orchestrator becomes a pass-through (ordinary dictation).
        """
        master = self._settings.intelligence_enabled
        return OrchestratorConfig(
            voice_edit_enabled=master and self._settings.voice_edit_enabled,
            snippets_enabled=master and self._settings.snippets_enabled,
            structure_enabled=master and self._settings.structure_enabled,
            developer_mode_enabled=master and self._settings.developer_mode_enabled,
        )

    def _update_home_protected(self, sz) -> None:
        """Reflect a Safe Zone block on the Home tab, if it exists. Guarded."""
        window = self._settings_window
        if window is None:
            return
        home = getattr(window, "home_tab", None)
        if home is None:
            return
        setter = getattr(home, "set_protected", None)
        if setter is None:
            return
        try:
            setter(sz.matched_entry or sz.app_name)
        except Exception as e:
            logger.debug(f"Home protected update skipped: {e}")

    def _on_engine_state_change(self, state: EngineState, message: str) -> None:
        if state in (EngineState.PROCESSING, EngineState.READY, EngineState.ERROR):
            if (
                self._transcription_worker is not None
                and self._transcription_worker.isRunning()
            ):
                return

        status_map = {
            EngineState.NOT_LOADED: TrayStatus.IDLE,
            EngineState.DOWNLOADING: TrayStatus.LOADING,
            EngineState.LOADING: TrayStatus.LOADING,
            EngineState.READY: TrayStatus.IDLE,
            EngineState.ERROR: TrayStatus.ERROR,
        }
        self._tray.set_status(status_map.get(state, TrayStatus.IDLE), message)

        if state == EngineState.DOWNLOADING:
            self._show_download_dialog()
        elif state in (EngineState.READY, EngineState.ERROR, EngineState.NOT_LOADED):
            self._hide_download_dialog(state == EngineState.READY)

    def _on_download_progress(self, progress: float) -> None:
        if self._download_dialog is not None:
            self._download_dialog.set_progress(progress)

    def _show_download_dialog(self) -> None:
        if self._download_dialog is None:
            self._download_dialog = DownloadDialog(model_name=self._settings.model_id)
            self._download_dialog.cancelled.connect(self._on_download_cancelled)
        self._download_dialog.show()

    def _hide_download_dialog(self, success: bool = True) -> None:
        if self._download_dialog is not None:
            self._download_dialog.finish(success)
            self._download_dialog = None

    def _on_download_cancelled(self) -> None:
        # Cancel the downloader owned by the background model-loading thread.
        # Do not unload the active transcription engine here: during startup
        # it may still be the previous engine, not the engine performing the
        # download.
        if self._model_loader_thread is not None:
            self._model_loader_thread.cancel()
        self._hide_download_dialog(success=False)

    def _start_recording(self) -> None:
        # Only start recording from IDLE/ERROR. Never start while already
        # recording, transcribing, or shutting down.
        if self._state not in (AppState.IDLE, AppState.ERROR, AppState.CANCELLED):
            logger.debug(
                f"Ignoring start_recording in state {self._state.name}"
            )
            return

        # Phase 8E Safe Zones: GATE before any audio is captured. If the current
        # foreground application is a user-designated protected app, recording
        # must not begin and no audio is recorded. Fail-safe: a detection error
        # or no match means NOT protected (dictation is never silently disabled
        # by a detection failure).
        if self._settings.safe_zones_enabled and self._settings.protected_apps:
            try:
                sz = is_protected(
                    self._settings.protected_apps,
                    enabled=self._settings.safe_zones_enabled,
                )
            except Exception as e:
                logger.debug(f"Safe-zone check failed (fail-safe, allowing): {e}")
                sz = None
            if sz is not None and sz.protected:
                logger.info(
                    f"Recording blocked by Safe Zone (app '{sz.matched_entry}')"
                )
                self._set_state(
                    AppState.IDLE, "SayIt paused — protected application"
                )
                self._update_home_protected(sz)
                return

        logger.debug("Starting audio recording")
        if self._recorder.start():
            import time

            self._recording_started_at = time.perf_counter()
            # Start a fresh privacy-safe timing record for this dictation. The
            # real job id is assigned at stop; use -1 as a provisional label.
            self._timing = PipelineTiming(job_id=-1)
            self._timing.mark("recording_start", self._recording_started_at)
            self._set_state(AppState.RECORDING)
            self._latest_audio_level = 0.0
            self._latest_audio_spectrum = []
            self._recording_toast.show_recording()
            self._audio_level_timer.start()
            logger.info("Recording started")
        else:
            error_msg = self._recorder.last_error or "Failed to start recording"
            # Recorder failed to start: it is not open, so we must not stay in
            # RECORDING. Return to a visible ERROR state (recoverable).
            self._set_state(AppState.ERROR, error_msg)
            logger.error(f"Recording error: {error_msg}")

    def _teardown_recording_ui(self) -> None:
        """Stop the level timer and hide the recording overlay. Idempotent."""
        self._audio_level_timer.stop()
        self._recording_toast.hide_recording()
        self._recording_toast.set_level(0.0)
        self._recording_toast.set_spectrum([])

    def _stop_recording(self) -> None:
        # Only meaningful while recording. Ignore stray release events in other
        # states (e.g. after an Esc cancellation already stopped the recorder).
        if self._state != AppState.RECORDING:
            logger.debug(f"Ignoring stop_recording in state {self._state.name}")
            return

        logger.debug("Stopping audio recording")
        import time

        stop_ts = time.perf_counter()
        audio_data = self._recorder.stop()
        self._teardown_recording_ui()
        if self._timing is not None:
            self._timing.mark("recording_stop", stop_ts)

        rec_duration = (
            time.perf_counter() - self._recording_started_at
            if self._recording_started_at is not None
            else None
        )

        if audio_data is None or len(audio_data) == 0:
            logger.warning("No audio data captured")
            self._set_state(AppState.IDLE)
            return

        sample_rate = self._settings.sample_rate
        audio_seconds = len(audio_data) / sample_rate if sample_rate else 0.0

        self._set_state(AppState.TRANSCRIBING)
        QApplication.processEvents()

        enhancement = self._settings.get_active_enhancement()

        # Assign this dictation an immutable job id and record it as the active
        # owner of text output. Signals carry the id so stale/cancelled
        # completions can be rejected.
        self._job_counter += 1
        job_id = self._job_counter
        self._active_job_id = job_id
        self._transcribe_started_at = time.perf_counter()
        if self._timing is not None:
            self._timing.job_id = job_id

        # Developer diagnostics only (no transcript text / no audio payload).
        rec_str = f"{rec_duration:.2f}s" if rec_duration is not None else "n/a"
        logger.info(
            f"[job {job_id}] recording captured: samples={len(audio_data)}, "
            f"audio={audio_seconds:.2f}s, held={rec_str}; starting transcription"
        )

        # Phase 8A: resolve the local context ONCE, now — while the user's
        # target application is still foreground — so the whole job is
        # deterministic. Fail-safe: resolve() never raises (returns Normal on
        # any error) and never blocks recording.
        context_resolution = None
        try:
            context_resolution = self._context_engine.resolve()
            self._last_context = context_resolution
            logger.info(
                f"[job {job_id}] context: {context_resolution.profile.value} "
                f"({context_resolution.source}); "
                f"detect={self._context_engine.last_detect_ms:.2f}ms"
            )
            self._update_home_context(context_resolution)
        except Exception as e:
            logger.debug(f"Context resolution skipped: {e}")

        self._transcription_worker = TranscriptionWorkerThread(
            transcriber=self._transcriber,
            audio_data=audio_data,
            sample_rate=self._settings.sample_rate,
            vocabulary_replacements=self._settings.vocabulary_replacements,
            llm_processor=self._llm_processor,
            enhancement=enhancement,
            parent=self,
            technical_correction_enabled=self._settings.technical_correction_enabled,
            structured_formatting_enabled=self._settings.structured_formatting_enabled,
            timing=self._timing,
            custom_vocabulary=self._settings.custom_vocabulary,
            context_resolution=context_resolution,
            orchestrator=self._orchestrator,
            snippets=snippets_from_any(self._settings.snippets),
            recent_output=self._output_buffer.current,
            post_asr_pipeline=self._get_post_asr_pipeline(),
        )
        self._transcription_worker.finished.connect(
            partial(self._on_transcription_complete, job_id)
        )
        self._transcription_worker.error.connect(
            partial(self._on_transcription_error, job_id)
        )
        self._transcription_worker.start()

    def _cancel_current(self) -> None:
        """Cancel the current dictation operation (Esc).

        No-op unless the app is actively recording or transcribing, so Esc is
        harmless when idle. Cancellation never inserts text:
        - RECORDING: stop the recorder, discard the audio, return to IDLE.
        - TRANSCRIBING: invalidate the job id (so any result is rejected) and
          ask the worker to cancel cooperatively. The worker finishes on its own
          time; its result is discarded by the stale-job guard.
        """
        if self._state == AppState.RECORDING:
            logger.info("Cancelling active recording (Esc)")
            try:
                self._recorder.stop()  # discard captured audio
            except Exception as e:
                logger.error(f"Error stopping recorder on cancel: {e}")
            self._teardown_recording_ui()
            # If a job id was somehow assigned, invalidate it defensively.
            self._active_job_id = None
            self._set_state(AppState.CANCELLED)
            self._set_state(AppState.IDLE)
            return

        if self._state == AppState.TRANSCRIBING:
            logger.info("Cancelling in-flight transcription (Esc)")
            # Invalidate ownership first: even if the worker completes, its
            # result will be rejected and cannot be inserted.
            self._active_job_id = None
            if self._transcription_worker is not None:
                self._transcription_worker.cancel()
            self._set_state(AppState.CANCELLED)
            self._set_state(AppState.IDLE)
            return

        logger.debug(f"Esc ignored in state {self._state.name}")

    def _on_transcription_complete(
        self,
        job_id: int,
        final_text: str,
        raw_text: str,
        enhanced_text: Optional[str],
        enhancement_name: Optional[str],
        cost: Optional[float],
        intel_meta: Optional[dict] = None,
    ) -> None:
        # Reject stale completions: if this result does not belong to the job
        # that currently owns output (e.g. the app moved on, shut down, or the
        # engine was reloaded while this worker was in flight), discard it so it
        # cannot insert into a newer context.
        if job_id != self._active_job_id:
            logger.warning(
                f"Discarding stale transcription result (job {job_id}, "
                f"active {self._active_job_id})"
            )
            return

        # This job is done and owned output; clear ownership and the worker
        # reference so the next recording can start. Done first so every return
        # path below leaves a clean slate.
        self._active_job_id = None
        self._transcription_worker = None

        import time

        asr_duration = (
            time.perf_counter() - self._transcribe_started_at
            if self._transcribe_started_at is not None
            else None
        )
        asr_str = f"{asr_duration:.2f}s" if asr_duration is not None else "n/a"

        # Check if transcription contains unknown tokens (model error)
        if _UNK_TOKEN_PATTERN in raw_text:
            logger.warning(
                f"[job {job_id}] transcription contained unknown tokens; discarding "
                f"({len(raw_text)} chars)"
            )
            self._record_transcription("[ERROR]", None, enhancement_name, cost)
            self._set_state(AppState.IDLE)
            return

        # Diagnostics only: lengths and timing, never transcript content.
        logger.info(
            f"[job {job_id}] transcription complete: "
            f"release->transcript={asr_str}, chars={len(final_text)}"
        )
        self._record_transcription(raw_text, enhanced_text, enhancement_name, cost)
        # The raw transcript is already recorded to history above, which is the
        # recovery backstop if insertion does not land.
        if self._timing is not None:
            self._timing.mark("insertion_start")
            self._timing.final_char_count = len(final_text)
        result = self._text_output.output_text(final_text)
        if self._timing is not None:
            self._timing.mark("insertion_end")

        if not result.copied:
            # Transcript never reached the clipboard. It is still held in memory
            # (and in history if the user enabled it).
            where = "history" if self._settings.history_enabled else "the app"
            logger.error(
                "Text insertion failed: could not copy to clipboard."
            )
            self._set_state(
                AppState.ERROR,
                f"Could not insert text. It's kept in {where}.",
            )
            return

        if not result.paste_issued:
            # Copied but the paste keystroke could not be issued. The transcript
            # is on the clipboard, so the user can paste it manually.
            logger.warning(
                "Paste keystroke could not be issued; transcript left on "
                "clipboard for manual paste."
            )
            self._set_state(
                AppState.ERROR,
                "Couldn't auto-paste. Transcript is on your clipboard.",
            )
            return

        # Success: reflect the actual transcript on Home (if open), then return
        # to idle. IDLE keeps the transcript card visible for review.
        logger.info(f"[job {job_id}] text inserted (clipboard paste issued)")
        if self._timing is not None:
            logger.info(self._timing.summary())

        # Phase 8H: maintain the bounded recent-output buffer so the NEXT
        # utterance can voice-edit this one. The buffer holds only the most
        # recent inserted text (in memory, never on disk). For a voice edit that
        # produced empty text (e.g. "scratch that"), clear the buffer.
        if final_text.strip():
            self._output_buffer.set_output(final_text)
        else:
            self._output_buffer.clear()

        # Phase 8H: if this was a voice edit, surface a brief, non-intrusive
        # note on Home (if open) describing what changed.
        if intel_meta and intel_meta.get("category") == "voice_edit":
            self._update_home_edit_note(intel_meta.get("reason", "Voice edit"))

        self._update_home(AppState.IDLE, transcript=final_text)
        self._set_state(AppState.IDLE)

    def _update_home_edit_note(self, note: str) -> None:
        """Show a brief voice-edit note on Home, if present. Guarded."""
        window = self._settings_window
        if window is None:
            return
        home = getattr(window, "home_tab", None)
        if home is None:
            return
        setter = getattr(home, "set_edit_note", None)
        if setter is None:
            return
        try:
            setter(note)
        except Exception as e:
            logger.debug(f"Home edit note skipped: {e}")

    def _on_transcription_error(self, job_id: int, error_message: str) -> None:
        # Ignore errors from stale/cancelled jobs (see _on_transcription_complete).
        if job_id != self._active_job_id:
            logger.warning(
                f"Discarding stale transcription error (job {job_id}, "
                f"active {self._active_job_id}): {error_message}"
            )
            return
        # The worker has finished (with an error); clear ownership and the
        # reference so the next recording can start.
        self._active_job_id = None
        self._transcription_worker = None
        logger.error(f"Background transcription failed: {error_message}")
        self._set_state(AppState.ERROR, error_message)

    def _init_llm_processor(self) -> None:
        has_config = (
            self._settings.llm_api_key
            or self._settings.active_enhancement_id
            or self._settings.llm_provider == "ollama"
        )
        if has_config:
            model_name = LLMProcessor.format_model_name(
                self._settings.llm_model, self._settings.llm_provider
            )
            self._llm_processor = LLMProcessor(
                model=model_name,
                api_key=self._settings.llm_api_key,
                api_base=self._settings.llm_api_base,
            )
            logger.info(
                f"LLM processor initialized: model={model_name}, api_base={self._settings.llm_api_base}"
            )
        else:
            self._llm_processor = None

    def _record_transcription(
        self,
        raw_text: str,
        enhanced_text: Optional[str],
        enhancement_name: Optional[str],
        cost_usd: Optional[float],
    ) -> None:
        # Always keep the latest transcript in memory for failed-insertion
        # recovery, regardless of the persistent-history setting.
        self._last_transcript = enhanced_text or raw_text

        # Persist to history.json only when the user has opted in. OFF by
        # default for privacy.
        if not self._settings.history_enabled:
            return

        record = TranscriptionRecord(
            timestamp=datetime.now().isoformat(),
            raw_text=raw_text,
            enhanced_text=enhanced_text,
            enhancement_name=enhancement_name,
            cost_usd=cost_usd,
        )
        add_history_record(record)
        logger.debug(f"Recorded transcription to history: {len(raw_text)} chars")

    def _show_settings(self) -> None:
        if self._settings_window is None:
            self._settings_window = SettingsWindow()
            self._settings_window.settings_changed.connect(self._on_settings_changed)

        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()
        self._update_home_speech_mode()

    def _on_settings_changed(self) -> None:
        old_model = self._transcriber.model_name
        old_whisper_threads = getattr(
            self._transcriber, "_whisper_num_threads", 4
        )

        self._settings = get_settings()

        self._recorder.sample_rate = self._settings.sample_rate
        self._recorder.device = self._settings.input_device
        self._hotkey_listener.update_settings(self._settings)

        # Keep the context engine reading from the current settings object.
        self._context_engine._settings = self._settings

        # Phase 8H: rebuild the orchestrator feature-config from new settings.
        self._orchestrator = IntelligenceOrchestrator(
            self._build_orchestrator_config()
        )
        # Phase 9K: drop the cached experimental pipeline so a flag/threshold
        # change (including disabling = rollback) takes effect on the next job.
        self._post_asr_pipeline = None

        self._init_llm_processor()

        model_changed = old_model != self._settings.model_id
        # A Whisper CPU-thread change also requires an engine reload so the new
        # thread count takes effect (the count is applied at model construction).
        # Reloading on this is safe and reuses the same deterministic path; for
        # Parakeet the thread setting is ignored by the backend anyway.
        threads_changed = (
            old_whisper_threads != self._settings.whisper_small_cpu_threads
        )
        if model_changed or threads_changed:
            logger.info(
                f"Reloading transcription engine (model: {old_model} -> "
                f"{self._settings.model_id}; whisper_threads: {old_whisper_threads} "
                f"-> {self._settings.whisper_small_cpu_threads})"
            )

            # Deterministic reload policy: a transcription may be holding a
            # reference to the current engine. We must not unload the engine
            # underneath a running worker. So we (1) invalidate the active job
            # so its result can never be inserted, (2) ask the worker to cancel
            # cooperatively, and (3) wait for it to actually finish before
            # unloading. The worker is never force-killed.
            if (
                self._transcription_worker is not None
                and self._transcription_worker.isRunning()
            ):
                logger.info(
                    "Invalidating and cancelling active transcription before reload"
                )
                self._active_job_id = None
                self._transcription_worker.cancel()
                self._transcription_worker.wait()
                self._transcription_worker = None

            self._transcriber.unload()

            if self._settings_window is not None:
                self._settings_window.set_loading(True)

            self._start_model_loading(self._settings.model_id, user_initiated=True)

        set_autostart(self._settings.auto_start_on_login, "SayIt")
        self._update_home_speech_mode()

    def _quit(self) -> None:
        logger.info("Shutting down application")
        # Enter the terminal state first so no late signal or timer can move the
        # app back into an active state during teardown.
        self._active_job_id = None
        self._set_state(AppState.SHUTTING_DOWN)

        # Stop any active recording and tear down its UI.
        try:
            if self._recorder.is_recording:
                self._recorder.stop()
            self._teardown_recording_ui()
        except Exception as e:
            logger.error(f"Error stopping recorder during shutdown: {e}")

        # Cooperatively cancel an in-flight model download/load first so
        # no QThread survives application teardown.
        if (
            self._model_loader_thread is not None
            and self._model_loader_thread.isRunning()
        ):
            self._model_loader_thread.cancel()
            self._model_loader_thread.wait()
        self._model_loader_thread = None

        # Cooperatively cancel an in-flight transcription and wait for it to
        # finish; never force-kill the thread.
        if (
            self._transcription_worker is not None
            and self._transcription_worker.isRunning()
        ):
            self._transcription_worker.cancel()
            self._transcription_worker.wait()
        self._transcription_worker = None

        self._hotkey_listener.stop()
        self._transcriber.unload()
        self._tray.hide()
        self._recording_toast.hide()
        QApplication.quit()
        logger.info("Application shutdown complete")

    def _capture_audio_level(self, level: float) -> None:
        self._latest_audio_level = level

    def _capture_audio_spectrum(self, spectrum: list[float]) -> None:
        self._latest_audio_spectrum = spectrum

    def _update_audio_level(self) -> None:
        self._recording_toast.set_level(self._latest_audio_level)
        self._recording_toast.set_spectrum(self._latest_audio_spectrum)

    def _start_model_loading(
        self, model_name: str, user_initiated: bool = False
    ) -> None:
        if (
            self._model_loader_thread is not None
            and self._model_loader_thread.isRunning()
        ):
            self._model_loader_thread.wait()

        self._loading_model_id = model_name
        self._load_user_initiated = user_initiated

        self._model_loader_thread = ModelLoaderThread(
            model_name=model_name, parent=self,
            whisper_num_threads=self._settings.whisper_small_cpu_threads,
        )
        self._model_loader_thread.state_changed.connect(self._on_engine_state_change)
        self._model_loader_thread.progress.connect(self._on_download_progress)
        self._model_loader_thread.finished.connect(self._on_model_loaded)
        self._model_loader_thread.start()

    def _on_model_loaded(self, success: bool, message: str) -> None:
        if success and self._model_loader_thread is not None:
            self._transcriber = self._model_loader_thread.engine
            logger.info(f"Model loading complete: {message}")
            self._fallback_attempted = False
        else:
            logger.error(f"Model loading failed: {message}")

            # Safe startup fallback: if a NON-user-initiated (startup/default)
            # load failed, the failed model is not already the fallback, and we
            # have not already fallen back, try the known-compatible model once.
            # Explicit user selections are never silently replaced — they show
            # the error below instead.
            from .core.settings.settings import FALLBACK_MODEL_ID

            can_fallback = (
                not self._load_user_initiated
                and not self._fallback_attempted
                and self._loading_model_id != FALLBACK_MODEL_ID
            )
            if can_fallback:
                self._fallback_attempted = True
                logger.warning(
                    f"Default model '{self._loading_model_id}' failed to load "
                    f"({message}); falling back to '{FALLBACK_MODEL_ID}'"
                )
                if self._settings_window is not None:
                    self._settings_window.set_loading(True)
                self._start_model_loading(FALLBACK_MODEL_ID, user_initiated=False)
                return

        if self._settings_window is not None:
            self._settings_window.set_loading(False)
            if success:
                self._settings_window.refresh_asr_model_list()

        # Don't override an active dictation's state with the model-load result.
        if self._state in (AppState.RECORDING, AppState.TRANSCRIBING):
            return

        if success:
            self._set_state(AppState.IDLE, message)
        else:
            self._set_state(AppState.ERROR, message)

    def run(self) -> None:
        logger.info(f"Starting {__app_name__} v{__version__}")
        logger.info(
            f"Settings: model={self._settings.model_id}, sample_rate={self._settings.sample_rate}"
        )

        logger.info(
            f"Starting hotkey listener: {self._settings.hotkey.to_display_string()}"
        )
        QTimer.singleShot(0, self._hotkey_listener.start)

        if not self._settings.start_minimized:
            self._show_settings()

        logger.info("Deferring model load to after UI is shown...")
        QTimer.singleShot(100, self._start_deferred_model_loading)

        logger.info("Application initialization complete")

    def _start_deferred_model_loading(self) -> None:
        logger.info("Starting deferred transcription model loading...")
        self._start_model_loading(self._settings.model_id)


def main():
    app = QApplication(sys.argv)
    # Technical identifier stays SayIt (settings/paths/autostart); the
    # user-facing display name is set separately.
    app.setApplicationName("SayIt")
    app.setApplicationDisplayName(__display_name__)
    app.setQuitOnLastWindowClosed(False)

    # Apply the shared calm theme and the code-drawn SayIt mark app-wide.
    from .ui.theme import STYLESHEET, sayit_icon

    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(sayit_icon(64))

    signal.signal(signal.SIGINT, lambda *args: QApplication.quit())

    settings = get_settings()

    # CI-only smoke mode: exercise the packaged Python/QT startup path without
    # opening the setup wizard or downloading a speech model. This is intentionally
    # environment-gated and never changes normal user behavior.
    if os.environ.get("SAYIT_LINUX_SMOKE_TEST") == "1":
        if sys.platform.startswith("linux"):
            import sounddevice as sd

            from . import _bundled_portaudio_path

            bundled = (
                _bundled_portaudio_path.resolve()
                if _bundled_portaudio_path is not None
                else None
            )
            loaded = (
                Path(sd._libname).resolve()
                if getattr(sd, "_libname", None)
                and str(getattr(sd, "_libname", "")).startswith("/")
                else None
            )
            if bundled is None or loaded is None or bundled != loaded:
                raise RuntimeError(
                    "Linux smoke test failed: sounddevice did not resolve the bundled "
                    "PortAudio runtime"
                )
        logger.info("Linux packaged launch smoke test passed")
        return

    if not settings.first_run_complete:
        wizard = SetupWizard()
        if wizard.exec() != SetupWizard.Accepted:
            sys.exit(0)

    transcribe_app = TranscribeApp()
    transcribe_app.run()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
