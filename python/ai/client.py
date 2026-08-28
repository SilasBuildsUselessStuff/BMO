"""Provider-independent AI interface and local Ollama implementation."""

from abc import ABC, abstractmethod
from threading import RLock
from typing import Any

import requests


class AIError(RuntimeError):
    """Raised when an AI response cannot be generated."""


class AIClient(ABC):
    """
    Common interface for an AI backend.

    The assistant depends on this interface rather than directly depending
    on Ollama. Another local or cloud provider can therefore be added later
    without rewriting the voice and GUI logic.
    """

    @abstractmethod
    def generate_response(self, user_text: str) -> str:
        """Generate BMO's response to one user message."""


class OllamaClient(AIClient):
    """
    Generate BMO responses through Ollama's local HTTP API.

    A small amount of recent conversation history is retained in memory.
    This allows BMO to understand follow-up requests such as "another one"
    and helps prevent repeated responses.

    This is temporary session context, not long-term memory. It disappears
    when the application closes.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        system_prompt: str,
        timeout: float = 120.0,
        keep_alive: str = "10m",
        temperature: float = 0.7,
        max_tokens: int = 120,
        history_turns: int = 6,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.system_prompt = system_prompt
        self.timeout = timeout
        self.keep_alive = keep_alive
        self.temperature = temperature
        self.max_tokens = max_tokens

        # One turn consists of one user message and one BMO response.
        self.history_turns = max(0, history_turns)
        self._history: list[tuple[str, str]] = []

        # Only one generation should modify conversation history at a time.
        self._generation_lock = RLock()

    def generate_response(self, user_text: str) -> str:
        """
        Generate a response using Ollama and recent conversation context.

        This method performs a blocking HTTP request. The BMO assistant calls
        it from its interaction worker rather than Tkinter's GUI thread.

        Raises:
            AIError: If the input is empty, Ollama is unavailable, the request
            fails, or Ollama returns an invalid response.
        """

        cleaned_text = user_text.strip()

        if not cleaned_text:
            raise AIError("Cannot generate a response for empty user input.")

        with self._generation_lock:
            messages = self._build_messages(cleaned_text)

            payload: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "keep_alive": self.keep_alive,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            }

            try:
                response = requests.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()

            except requests.Timeout as error:
                raise AIError(
                    f"Ollama did not respond within "
                    f"{self.timeout:g} seconds."
                ) from error

            except requests.ConnectionError as error:
                raise AIError(
                    "Could not connect to Ollama. "
                    "Make sure Ollama is running."
                ) from error

            except requests.HTTPError as error:
                detail = self._extract_error_detail(response)
                raise AIError(
                    f"Ollama returned an HTTP error: {detail}"
                ) from error

            except requests.RequestException as error:
                raise AIError(
                    f"Ollama request failed: {error}"
                ) from error

            try:
                result = response.json()
            except ValueError as error:
                raise AIError(
                    "Ollama returned a response that was not valid JSON."
                ) from error

            message = result.get("message")

            if not isinstance(message, dict):
                raise AIError(
                    "Ollama response did not contain a message."
                )

            content = message.get("content")

            if not isinstance(content, str):
                raise AIError(
                    "Ollama response did not contain valid text."
                )

            content = content.strip()

            if not content:
                raise AIError("Ollama returned an empty response.")

            # Only successful interactions are added to history.
            self._history.append((cleaned_text, content))
            self._trim_history()

            return content

    def clear_history(self) -> None:
        """Forget all temporary conversation context."""

        with self._generation_lock:
            self._history.clear()

    @property
    def history_size(self) -> int:
        """Return the number of stored user/BMO exchanges."""

        with self._generation_lock:
            return len(self._history)

    def _build_messages(
        self,
        current_user_text: str,
    ) -> list[dict[str, str]]:
        """Build the system prompt, recent history, and current message."""

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": self.system_prompt,
            }
        ]

        for previous_user_text, previous_bmo_response in self._history:
            messages.append(
                {
                    "role": "user",
                    "content": previous_user_text,
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": previous_bmo_response,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": current_user_text,
            }
        )

        return messages

    def _trim_history(self) -> None:
        """Keep only the configured number of recent exchanges."""

        if self.history_turns == 0:
            self._history.clear()
            return

        if len(self._history) > self.history_turns:
            self._history = self._history[-self.history_turns:]

    @staticmethod
    def _extract_error_detail(response: requests.Response) -> str:
        """Extract a useful error message from a failed Ollama response."""

        try:
            result = response.json()
            detail = result.get("error")

            if isinstance(detail, str) and detail.strip():
                return detail.strip()

        except ValueError:
            pass

        if response.text.strip():
            return response.text.strip()

        return f"HTTP {response.status_code}"


//.\.venv\Scripts\python.exe -m py_compile ai\client.py


//@'
from ai.client import OllamaClient
from ai.personality import BMO_SYSTEM_PROMPT
from config import (
    OLLAMA_BASE_URL,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MAX_TOKENS,
    OLLAMA_MODEL,
    OLLAMA_TEMPERATURE,
    OLLAMA_TIMEOUT,
)

client = OllamaClient(
    base_url=OLLAMA_BASE_URL,
    model=OLLAMA_MODEL,
    system_prompt=BMO_SYSTEM_PROMPT,
    timeout=OLLAMA_TIMEOUT,
    keep_alive=OLLAMA_KEEP_ALIVE,
    temperature=OLLAMA_TEMPERATURE,
    max_tokens=OLLAMA_MAX_TOKENS,
)

messages = [
    "Tell me a short joke.",
    "Tell me another one. Do not repeat the previous joke.",
    "One more different joke, please.",
]

for message in messages:
    print()
    print("You:", message)
    print("BMO:", client.generate_response(message))
    print("Stored exchanges:", client.history_size)
'@ | .\.venv\Scripts\python.exe -
