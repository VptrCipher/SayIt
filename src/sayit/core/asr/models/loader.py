from PySide6.QtCore import QThread, Signal

from ....utils.logger import get_logger
from ..transcriber import EngineState, TranscriptionEngine

logger = get_logger(__name__)


class ModelLoaderThread(QThread):
    finished = Signal(bool, str)
    progress = Signal(float)
    state_changed = Signal(EngineState, str)

    def __init__(self, model_name: str, parent=None, whisper_num_threads: int = 4):
        super().__init__(parent)
        self._model_name = model_name
        self._whisper_num_threads = whisper_num_threads
        self._engine: TranscriptionEngine = None

    def run(self):
        logger.info(f"Background loading model: {self._model_name}")

        try:
            self._engine = TranscriptionEngine(
                model_name=self._model_name,
                on_state_change=self._on_state_change,
                on_download_progress=self._on_progress,
                whisper_num_threads=self._whisper_num_threads,
            )

            self._engine.load_model()

            message = "Model loaded on CPU"
            logger.info(f"Background model loading complete: {message}")
            self.finished.emit(True, message)

        except Exception as e:
            message = f"Error loading model: {e}"
            logger.exception(f"Background model loading error: {e}")
            self.finished.emit(False, message)

    def _on_state_change(self, state: EngineState, message: str):
        self.state_changed.emit(state, message)

    def _on_progress(self, value: float):
        self.progress.emit(value)

    def cancel(self) -> None:
        """Request cooperative cancellation of the current model download."""
        if self._engine is not None:
            self._engine.cancel_model_download()

    @property
    def engine(self) -> TranscriptionEngine:
        return self._engine
