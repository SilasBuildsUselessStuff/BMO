"""Local Windows text-to-speech support for BMO."""

from threading import Event, RLock
from typing import Optional

import pythoncom
import win32com.client


class TTSError(RuntimeError):
    """Raised when text-to-speech cannot be completed."""


class WindowsTTS:
    """
    Speak text through Windows SAPI.

    Speech runs on whichever thread calls speak(). The BMO assistant will
    call it from its background interaction thread so Tkinter remains
    responsive.

    A cancellation event allows application shutdown to interrupt speech.
    """

    # Windows SAPI speech flags.
    _ASYNC = 1
    _PURGE_BEFORE_SPEAK = 2

    def __init__(
        self,
        voice_name: Optional[str] = None,
        rate: int = 1,
        volume: int = 100,
    ) -> None:
        self.voice_name = voice_name
        self.rate = max(-10, min(10, rate))
        self.volume = max(0, min(100, volume))

        self._lock = RLock()
        self._cancel_event = Event()
        self._speaking = False

    @property
    def is_speaking(self) -> bool:
        """Return whether a speech operation is currently active."""

        with self._lock:
            return self._speaking

    def speak(self, text: str) -> None:
        """
        Speak text through the default Windows audio output.

        This is a blocking method from the calling thread's perspective.
        The GUI remains responsive when it is called from a worker thread.

        Raises:
            TTSError: If the text is empty, the requested voice cannot be
            found, or Windows cannot synthesize the speech.
        """

        cleaned_text = text.strip()

        if not cleaned_text:
            raise TTSError("Cannot speak empty text.")

        self._cancel_event.clear()

        with self._lock:
            if self._speaking:
                raise TTSError("Text-to-speech is already active.")

            self._speaking = True

        # Every thread using Windows COM must initialize COM for itself.
        pythoncom.CoInitialize()

        speaker = None

        try:
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Rate = self.rate
            speaker.Volume = self.volume

            if self.voice_name:
                self._select_voice(speaker, self.voice_name)

            # Start asynchronously within this worker thread. Polling allows
            # cancel() to interrupt speech during application shutdown.
            speaker.Speak(cleaned_text, self._ASYNC)

            while not speaker.WaitUntilDone(100):
                if self._cancel_event.is_set():
                    speaker.Speak(
                        "",
                        self._ASYNC | self._PURGE_BEFORE_SPEAK,
                    )
                    break

        except TTSError:
            raise

        except Exception as error:
            raise TTSError(
                f"Windows text-to-speech failed: {error}"
            ) from error

        finally:
            if speaker is not None and self._cancel_event.is_set():
                try:
                    speaker.Speak(
                        "",
                        self._ASYNC | self._PURGE_BEFORE_SPEAK,
                    )
                except Exception:
                    pass

            with self._lock:
                self._speaking = False

            pythoncom.CoUninitialize()

    def cancel(self) -> None:
        """
        Request cancellation of current speech.

        The worker executing speak() notices this event and purges its SAPI
        speech queue.
        """

        self._cancel_event.set()

    @staticmethod
    def available_voices() -> list[str]:
        """Return descriptions of all Windows SAPI voices."""

        pythoncom.CoInitialize()

        try:
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            return [
                voice.GetDescription()
                for voice in speaker.GetVoices()
            ]
        except Exception as error:
            raise TTSError(
                f"Could not list Windows voices: {error}"
            ) from error
        finally:
            pythoncom.CoUninitialize()

    @staticmethod
    def _select_voice(speaker: object, requested_name: str) -> None:
        """
        Select the first installed voice whose description contains the
        configured name, ignoring capitalization.
        """

        requested = requested_name.casefold()

        for voice in speaker.GetVoices():
            description = voice.GetDescription()

            if requested in description.casefold():
                speaker.Voice = voice
                return

        raise TTSError(
            f"Windows voice containing '{requested_name}' was not found."
        )

  //.\.venv\Scripts\python.exe -c "from voice.tts import WindowsTTS, TTSError; print('TTS module loaded successfully')"

//.\.venv\Scripts\python.exe -c "from voice.tts import WindowsTTS; print(*WindowsTTS.available_voices(), sep='\n')"

    @'
from config import TTS_RATE, TTS_VOICE_NAME, TTS_VOLUME
from voice.tts import WindowsTTS

tts = WindowsTTS(
    voice_name=TTS_VOICE_NAME,
    rate=TTS_RATE,
    volume=TTS_VOLUME,
)

print("Speaking...")
tts.speak("Hello! BMO can talk now. This is very exciting!")
print("Finished speaking.")
'@ | .\.venv\Scripts\python.exe -



@'
import time
from threading import Thread

from voice.tts import WindowsTTS

tts = WindowsTTS(rate=0)

speech_thread = Thread(
    target=tts.speak,
    args=(
        "This is a deliberately long sentence that should stop before "
        "BMO reaches the end because we are testing speech cancellation.",
    ),
)

speech_thread.start()
time.sleep(1)

print("Cancelling speech...")
tts.cancel()

speech_thread.join()
print("Speaking:", tts.is_speaking)
print("Cancellation test finished.")
'@ | .\.venv\Scripts\python.exe -
