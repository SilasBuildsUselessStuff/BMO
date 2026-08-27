"""Provider-independent text-to-speech support for BMO."""

import re
from abc import ABC, abstractmethod
from threading import Event, RLock
from typing import Optional

import pythoncom
import win32com.client


class TTSError(RuntimeError):
    """Raised when text-to-speech cannot be completed."""


def prepare_text_for_speech(
    text: str,
    bmo_pronunciation: str = "Beemo",
) -> str:
    """
    Prepare display text for speech synthesis.

    The canonical name remains written as "BMO" everywhere in the
    application. Only the temporary text passed to the speech engine uses
    the phonetic spelling "Beemo".

    Examples:
        "Hello, BMO!" -> "Hello, Beemo!"
        "BMO's game"  -> "Beemo's game"

    This prevents Windows SAPI from saying "B M O".
    """

    prepared = text.strip()

    if not prepared:
        return ""

    # Match BMO as a complete term while preserving words that merely contain
    # those letters.
    prepared = re.sub(
        r"\bBMO\b",
        bmo_pronunciation,
        prepared,
        flags=re.IGNORECASE,
    )

    return prepared


class TTSProvider(ABC):
    """
    Common interface for a text-to-speech backend.

    BMOAssistant will depend on this interface instead of Windows SAPI.
    A neural local voice can therefore replace WindowsTTS later without
    changing the state machine, GUI, or interaction pipeline.
    """

    @property
    @abstractmethod
    def is_speaking(self) -> bool:
        """Return whether speech is currently active."""

    @abstractmethod
    def speak(self, text: str) -> None:
        """
        Speak the supplied text.

        Implementations may block the calling worker thread until playback
        finishes, but they must never be called directly on Tkinter's thread.
        """

    @abstractmethod
    def cancel(self) -> None:
        """Request cancellation of the active speech operation."""


class WindowsTTS(TTSProvider):
    """
    Speak through Windows SAPI.

    This is the initial TTS backend used to validate BMO's complete voice
    loop. It can later be replaced with a local neural implementation that
    implements the same TTSProvider interface.
    """

    # Windows SAPI speech flags.
    _ASYNC = 1
    _PURGE_BEFORE_SPEAK = 2

    def __init__(
        self,
        voice_name: Optional[str] = None,
        rate: int = 1,
        volume: int = 100,
        bmo_pronunciation: str = "Beemo",
    ) -> None:
        self.voice_name = voice_name
        self.rate = max(-10, min(10, rate))
        self.volume = max(0, min(100, volume))
        self.bmo_pronunciation = bmo_pronunciation

        self._lock = RLock()
        self._cancel_event = Event()
        self._speaking = False

    @property
    def is_speaking(self) -> bool:
        """Return whether speech is currently active."""

        with self._lock:
            return self._speaking

    def speak(self, text: str) -> None:
        """
        Speak text through the default Windows audio output.

        The canonical text is converted to a speech-friendly version before
        it reaches SAPI. The original string is not modified.

        This method blocks its calling thread while audio is playing.
        BMOAssistant will call it from a background worker thread.

        Raises:
            TTSError: If text is empty, speech is already active, the selected
            voice cannot be found, or Windows SAPI fails.
        """

        cleaned_text = text.strip()

        if not cleaned_text:
            raise TTSError("Cannot speak empty text.")

        spoken_text = prepare_text_for_speech(
            cleaned_text,
            self.bmo_pronunciation,
        )

        with self._lock:
            if self._speaking:
                raise TTSError("Text-to-speech is already active.")

            self._cancel_event.clear()
            self._speaking = True

        # Each thread that uses Windows COM must initialize it independently.
        pythoncom.CoInitialize()

        speaker = None

        try:
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Rate = self.rate
            speaker.Volume = self.volume

            if self.voice_name:
                self._select_voice(speaker, self.voice_name)

            # SAPI speaks asynchronously within this worker. Polling lets us
            # notice a cancellation request during application shutdown.
            speaker.Speak(spoken_text, self._ASYNC)

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
        Request cancellation of active speech.

        The worker running speak() notices this event and purges the SAPI
        speech queue.
        """

        self._cancel_event.set()

    @staticmethod
    def available_voices() -> list[str]:
        """Return descriptions of all installed Windows SAPI voices."""

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
    def _select_voice(
        speaker: object,
        requested_name: str,
    ) -> None:
        """
        Select the first installed voice whose description contains the
        requested name, ignoring capitalization.
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

//.\.venv\Scripts\python.exe -c "from voice.tts import TTSProvider, WindowsTTS, TTSError; print('Modular TTS loaded successfully'); print('WindowsTTS is a TTSProvider:', issubclass(WindowsTTS, TTSProvider))"

//@'
from voice.tts import prepare_text_for_speech

examples = [
    "Hello, BMO!",
    "BMO is ready for an adventure.",
    "This is BMO's favorite game.",
    "The name is bmo.",
    "The submarine moved below us.",
]

for original in examples:
    spoken = prepare_text_for_speech(original)
    print(f"Display: {original}")
    print(f"Speech:  {spoken}")
    print()
'@ | .\.venv\Scripts\python.exe -
