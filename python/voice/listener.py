"""Non-blocking PC microphone recording for BMO."""

from threading import RLock
from typing import Optional

import numpy as np
import sounddevice as sd


class MicrophoneError(RuntimeError):
    """Raised when microphone recording cannot start or stop correctly."""


class MicrophoneListener:
    """
    Record audio from the PC microphone using a background audio stream.

    sounddevice invokes _audio_callback() from its own audio thread. The
    application can therefore remain responsive while recording continues.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        dtype: str = "float32",
        device: Optional[int | str] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.device = device

        self._lock = RLock()
        self._stream: Optional[sd.InputStream] = None
        self._audio_chunks: list[np.ndarray] = []
        self._recording = False
        self._last_status: Optional[str] = None

    @property
    def is_recording(self) -> bool:
        """Return whether microphone recording is currently active."""

        with self._lock:
            return self._recording

    @property
    def last_status(self) -> Optional[str]:
        """
        Return the latest audio-stream warning.

        This may contain information about an input overflow or another
        sounddevice status condition.
        """

        with self._lock:
            return self._last_status

    def start_recording(self) -> None:
        """
        Start recording from the configured microphone.

        This method starts a callback-based audio stream and then returns.
        Recording continues in sounddevice's background audio thread.

        Raises:
            MicrophoneError: If the microphone stream cannot be opened.
        """

        with self._lock:
            if self._recording:
                return

            self._audio_chunks = []
            self._last_status = None

        try:
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                device=self.device,
                callback=self._audio_callback,
            )
            stream.start()

        except Exception as error:
            # Ensure a partially created stream does not remain open.
            try:
                if "stream" in locals():
                    stream.close()
            except Exception:
                pass

            raise MicrophoneError(
                f"Could not start microphone recording: {error}"
            ) from error

        with self._lock:
            self._stream = stream
            self._recording = True

    def stop_recording(self) -> np.ndarray:
        """
        Stop recording and return all captured audio samples.

        The returned array has shape:

            (number_of_samples, channels)

        For the initial mono configuration, its shape will be:

            (number_of_samples, 1)

        Raises:
            MicrophoneError: If recording is not active or cannot be stopped.
        """

        with self._lock:
            if not self._recording or self._stream is None:
                raise MicrophoneError("Microphone is not currently recording.")

            stream = self._stream

            # Mark recording as stopped before closing the stream so that a
            # late callback cannot append unwanted data.
            self._recording = False
            self._stream = None

        stop_error: Optional[Exception] = None

        try:
            stream.stop()
        except Exception as error:
            stop_error = error
        finally:
            try:
                stream.close()
            except Exception as error:
                if stop_error is None:
                    stop_error = error

        with self._lock:
            chunks = self._audio_chunks
            self._audio_chunks = []

        if stop_error is not None:
            raise MicrophoneError(
                f"Could not stop microphone recording cleanly: {stop_error}"
            ) from stop_error

        if not chunks:
            return np.empty(
                (0, self.channels),
                dtype=self.dtype,
            )

        return np.concatenate(chunks, axis=0)

    def cancel_recording(self) -> None:
        """
        Stop recording and discard the captured audio.

        This is useful during application shutdown or after an error.
        """

        with self._lock:
            stream = self._stream
            self._stream = None
            self._recording = False
            self._audio_chunks = []

        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass

            try:
                stream.close()
            except Exception:
                pass

    def _audio_callback(
        self,
        input_data: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        """
        Receive a block of microphone samples from sounddevice.

        The callback must remain short because it runs on the audio thread.
        Decisions and transcription must not happen here.
        """

        del frames, time_info

        with self._lock:
            if status:
                self._last_status = str(status)

            if not self._recording:
                return

            # sounddevice reuses its input buffer, so a copy is required.
            self._audio_chunks.append(input_data.copy())


//.\.venv\Scripts\python.exe -c "from voice.listener import MicrophoneListener, MicrophoneError; print('Microphone listener loaded successfully')"
//.\.venv\Scripts\python.exe -c "import time; import numpy as np; from config import AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, AUDIO_DTYPE, AUDIO_INPUT_DEVICE; from voice.listener import MicrophoneListener; listener = MicrophoneListener(AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, AUDIO_DTYPE, AUDIO_INPUT_DEVICE); print('Starting recording...'); listener.start_recording(); print('Recording:', listener.is_recording); print('Speak now for 3 seconds...'); time.sleep(3); audio = listener.stop_recording(); print('Recording:', listener.is_recording); print('Shape:', audio.shape); print('Duration:', round(len(audio) / AUDIO_SAMPLE_RATE, 2), 'seconds'); print('Peak:', float(np.max(np.abs(audio))) if audio.size else 0.0); print('Status:', listener.last_status)"
//.\.venv\Scripts\python.exe -c "import time; from voice.listener import MicrophoneListener; listener = MicrophoneListener(); listener.start_recording(); print('Before cancel:', listener.is_recording); time.sleep(1); listener.cancel_recording(); print('After cancel:', listener.is_recording); print('Recording cancelled normally')"
