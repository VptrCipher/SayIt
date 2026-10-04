import gc
import os
import time
from enum import Enum, auto
from typing import Callable, Optional

import numpy as np

from ...utils.logger import get_logger
from ..audio.audio_processor import AudioProcessor, needs_chunking
from .backends import SherpaOnnxBackend, TranscriptionResult
from .models.downloader import ModelDownloader
from .models.registry import get_model_by_id, is_model_downloaded


class EngineState(Enum):
    NOT_LOADED = auto()
    DOWNLOADING = auto()
    LOADING = auto()
    READY = auto()
    PROCESSING = auto()
    ERROR = auto()


class TranscriptionEngine:
    BACKEND_NAME = "SHERPA_ONNX"

    def __init__(
        self,
        model_name: str = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8",
        on_state_change: Optional[Callable[[EngineState, str], None]] = None,
        on_download_progress: Optional[Callable[[float], None]] = None,
        whisper_num_threads: int = 4,
    ):
        self.model_name = model_name
        self.on_state_change = on_state_change
        self.on_download_progress = on_download_progress
        # Whisper-only opt-in CPU thread count (bounded {4,6,8} by settings;
        # default 4). Passed to the backend only for whisper models; the
        # transducer (Parakeet) path ignores it entirely.
        self._whisper_num_threads = whisper_num_threads
        self._backend: Optional[SherpaOnnxBackend] = None
        self._model_downloader: Optional[ModelDownloader] = None
        self._state = EngineState.NOT_LOADED
        self._device = "cpu"  # Will be updated by backend load
        self._audio_processor = AudioProcessor()
        self.logger = get_logger(__name__)
        # Phase 6H diagnostics: count ASR backend invocations and the number of
        # chunks the last transcribe_chunked produced. Counters only; never any
        # transcript content.
        self._invocation_count = 0
        self._last_chunk_count = 0

    @property
    def last_invocation_count(self) -> int:
        """ASR backend calls made during the last transcribe_chunked call."""
        return self._last_chunk_count or self._invocation_count

    @property
    def last_chunk_count(self) -> int:
        """Chunks produced by the last transcribe_chunked call (1 if one-shot)."""
        return self._last_chunk_count

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def is_ready(self) -> bool:
        return self._state == EngineState.READY

    @property
    def device(self) -> str:
        if self._backend and self._backend.is_loaded:
            return self._backend.device
        return self._device

    @property
    def backend_name(self) -> str:
        return self.BACKEND_NAME

    def _set_state(self, state: EngineState, message: str = "") -> None:
        self._state = state
        if self.on_state_change:
            self.on_state_change(state, message)

    def load_model(self) -> bool:
        if self._backend is not None and self._backend.is_loaded:
            return True

        self._set_state(
            EngineState.LOADING,
            f"Loading {self.backend_name} model: {self.model_name}...",
        )
        self._backend = SherpaOnnxBackend()
        self._backend.load(
            model_path=self.model_name,
            on_progress=self.on_download_progress,
            whisper_num_threads=self._whisper_num_threads,
        )

        self._set_state(
            EngineState.READY,
            f"Model loaded on {self._backend.device.upper()} ({self.backend_name})",
        )
        return True

    def transcribe(
        self, audio_data: np.ndarray, sample_rate: int = 16000
    ) -> Optional[str]:
        if not self.is_ready:
            try:
                self.load_model()
            except Exception as e:
                self._set_state(EngineState.ERROR, f"Failed to load model: {e}")
                return None

        self._set_state(EngineState.PROCESSING, "Transcribing...")

        start_time = time.time()

        try:
            result: TranscriptionResult = self._backend.transcribe(
                audio_data=audio_data, sample_rate=sample_rate
            )

            processing_time = time.time() - start_time
            audio_duration = len(audio_data) / sample_rate

            if processing_time > 0:
                rtf = audio_duration / processing_time
                self.logger.debug(
                    f"Transcription finished: audio_len={audio_duration:.2f}s, "
                    f"time={processing_time:.2f}s, speed={rtf:.2f}x"
                )

                if result.text:
                    cps = len(result.text) / processing_time
                    self.logger.debug(f"Transcription speed: {cps:.2f} chars/sec")

            self._set_state(EngineState.READY, "Ready")
            return result.text

        except Exception as e:
            self._set_state(EngineState.ERROR, f"Transcription failed: {e}")
            return None

    def transcribe_chunked(
        self, audio_data: np.ndarray, sample_rate: int = 16000
    ) -> Optional[str]:
        if not needs_chunking(audio_data, sample_rate):
            # One-shot path: a single offline decode (the common case).
            self._last_chunk_count = 1
            return self.transcribe(audio_data, sample_rate)

        from ...utils.logger import get_logger

        logger = get_logger(__name__)

        chunks = self._audio_processor.split_audio(audio_data, sample_rate)
        self._last_chunk_count = len(chunks)
        logger.info(f"Processing {len(chunks)} audio chunks")
        transcriptions = []
        for i, chunk in enumerate(chunks):
            logger.debug(f"Transcribing chunk {i+1}/{len(chunks)}")
            text = self.transcribe(chunk, sample_rate)
            if text:
                transcriptions.append(text)

        combined = self._audio_processor.combine_transcriptions(transcriptions)
        logger.info(f"Combined {len(transcriptions)} transcriptions")

        return combined

    def transcribe_with_metadata(
        self, audio_data: np.ndarray, sample_rate: int = 16000
    ) -> Optional[TranscriptionResult]:
        if not self.is_ready:
            try:
                self.load_model()
            except Exception as e:
                self._set_state(EngineState.ERROR, f"Failed to load model: {e}")
                return None

        self._set_state(EngineState.PROCESSING, "Transcribing...")

        start_time = time.time()

        try:
            result = self._backend.transcribe(
                audio_data=audio_data, sample_rate=sample_rate
            )

            processing_time = time.time() - start_time
            audio_duration = len(audio_data) / sample_rate

            if processing_time > 0:
                rtf = audio_duration / processing_time
                self.logger.debug(
                    f"Transcription finished: audio_len={audio_duration:.2f}s, "
                    f"time={processing_time:.2f}s, speed={rtf:.2f}x"
                )

            self._set_state(EngineState.READY, "Ready")
            return result

        except Exception as e:
            self._set_state(EngineState.ERROR, f"Transcription failed: {e}")
            return None

    def unload(self) -> None:
        if self._backend is not None:
            self._backend.unload()
            self._backend = None

        gc.collect()
        self._set_state(EngineState.NOT_LOADED, "Model unloaded")

    def switch_model(self, model_name: str) -> bool:
        self.unload()
        self.model_name = model_name
        return self.load_model()

    def is_model_cached(self) -> bool:
        backend = SherpaOnnxBackend()
        return backend.is_model_cached(self.model_name)
