"""Local Whisper speech-to-text support for BMO."""

from threading import RLock
from typing import Optional

import numpy as np
from faster_whisper import WhisperModel


class TranscriptionError(RuntimeError):
    """Raised when audio cannot be transcribed."""


class WhisperTranscriber:
    """
    Convert recorded audio into text using a local faster-whisper model.

    The model is loaded lazily. Creating this object does not immediately
    download or load the model. That happens during load_model() or the first
    call to transcribe().
    """

    def __init__(
        self,
        model_name: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "en",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.language = language

        self._model: Optional[WhisperModel] = None
        self._lock = RLock()

    @property
    def is_loaded(self) -> bool:
        """Return whether the Whisper model is currently loaded."""

        with self._lock:
            return self._model is not None

    def load_model(self) -> None:
        """
        Load the configured Whisper model.

        The first call may download the model from the internet. Later calls
        use the locally cached model and return without loading it again.

        Raises:
            TranscriptionError: If the model cannot be downloaded or loaded.
        """

        with self._lock:
            if self._model is not None:
                return

            try:
                self._model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                )
            except Exception as error:
                raise TranscriptionError(
                    f"Could not load Whisper model "
                    f"'{self.model_name}': {error}"
                ) from error

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Convert a NumPy audio array into text.

        Audio from MicrophoneListener normally has the shape:

            (number_of_samples, 1)

        faster-whisper expects one-dimensional mono float32 samples, so this
        method prepares the audio before passing it to the model.

        Returns:
            The combined and cleaned transcript. An empty string is returned
            when Whisper detects no speech.

        Raises:
            TranscriptionError: If audio is invalid or transcription fails.
        """

        prepared_audio = self._prepare_audio(audio)

        if prepared_audio.size == 0:
            raise TranscriptionError("No audio was recorded.")

        self.load_model()

        with self._lock:
            model = self._model

            if model is None:
                raise TranscriptionError("Whisper model is not loaded.")

            try:
                segments, _information = model.transcribe(
                    prepared_audio,
                    language=self.language,
                    beam_size=5,
                    vad_filter=True,
                    condition_on_previous_text=False,
                )

                # faster-whisper returns a segment generator. Iterating over it
                # performs the actual transcription.
                transcript_parts = [
                    segment.text.strip()
                    for segment in segments
                    if segment.text.strip()
                ]

            except Exception as error:
                raise TranscriptionError(
                    f"Whisper transcription failed: {error}"
                ) from error

        return " ".join(transcript_parts).strip()

    @staticmethod
    def _prepare_audio(audio: np.ndarray) -> np.ndarray:
        """Convert recorded audio to contiguous mono float32 samples."""

        if not isinstance(audio, np.ndarray):
            raise TranscriptionError(
                "Audio must be provided as a NumPy array."
            )

        if audio.ndim == 1:
            mono_audio = audio
        elif audio.ndim == 2:
            if audio.shape[1] == 0:
                raise TranscriptionError("Audio has no channels.")

            # Average multiple channels if stereo input is used later.
            mono_audio = np.mean(audio, axis=1)
        else:
            raise TranscriptionError(
                f"Unsupported audio shape: {audio.shape}"
            )

        return np.ascontiguousarray(
            mono_audio,
            dtype=np.float32,
        )

//.\.venv\Scripts\python.exe -c "from voice.whisper import WhisperTranscriber, TranscriptionError; print('Whisper module loaded successfully')"
  //.\.venv\Scripts\python.exe -c "from config import WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, WHISPER_LANGUAGE; from voice.whisper import WhisperTranscriber; transcriber = WhisperTranscriber(WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, WHISPER_LANGUAGE); print('Loaded before:', transcriber.is_loaded); print('Loading Whisper model...'); transcriber.load_model(); print('Loaded after:', transcriber.is_loaded); print('Whisper model is ready')"
  //.\.venv\Scripts\python.exe -c "import time; import numpy as np; from config import AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, AUDIO_DTYPE, AUDIO_INPUT_DEVICE, WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, WHISPER_LANGUAGE; from voice.listener import MicrophoneListener; from voice.whisper import WhisperTranscriber; listener = MicrophoneListener(AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, AUDIO_DTYPE, AUDIO_INPUT_DEVICE); transcriber = WhisperTranscriber(WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, WHISPER_LANGUAGE); print('Speak clearly for 5 seconds...'); listener.start_recording(); time.sleep(5); audio = listener.stop_recording(); print('Recorded duration:', round(len(audio) / AUDIO_SAMPLE_RATE, 2), 'seconds'); print('Peak:', float(np.max(np.abs(audio))) if audio.size else 0.0); print('Transcribing...'); text = transcriber.transcribe(audio); print('Transcript:', repr(text))"
  //.\.venv\Scripts\python.exe -c "import time; from config import AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, AUDIO_DTYPE, AUDIO_INPUT_DEVICE, WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, WHISPER_LANGUAGE; from voice.listener import MicrophoneListener; from voice.whisper import WhisperTranscriber; listener = MicrophoneListener(AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, AUDIO_DTYPE, AUDIO_INPUT_DEVICE); transcriber = WhisperTranscriber(WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, WHISPER_LANGUAGE); print('Remain quiet for 3 seconds...'); listener.start_recording(); time.sleep(3); audio = listener.stop_recording(); print('Transcribing silence...'); text = transcriber.transcribe(audio); print('Transcript:', repr(text))"
  //.\.venv\Scripts\python.exe -c "import numpy as np; from voice.whisper import WhisperTranscriber, TranscriptionError; transcriber = WhisperTranscriber(); audio = np.empty((0, 1), dtype='float32'); print('Testing empty audio...'); transcriber.transcribe(audio)"
  .\.venv\Scripts\python.exe -c "from voice.whisper import WhisperTranscriber, TranscriptionError; print('Whisper module loaded successfully')"
