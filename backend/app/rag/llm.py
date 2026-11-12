"""Chat model boundary. The service depends on the ChatModel protocol, not on OpenAI directly."""

from typing import Protocol

from openai import OpenAI

MAX_RETRIES = 3  # SDK retries with exponential backoff on 429/5xx/timeouts


class ChatModel(Protocol):
    def complete(self, system: str, user: str) -> str:
        """An empty system prompt sends only the user message."""
        ...


class LLMError(RuntimeError):
    """The language model call failed or returned nothing."""


class OpenAIChatModel:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout_s: float,
    ):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set (see .env.example)")
        self._client = OpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout_s, max_retries=MAX_RETRIES
        )
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def complete(self, system: str, user: str) -> str:
        try:
            messages = [{"role": "system", "content": system}] if system else []
            messages.append({"role": "user", "content": user})
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
        except Exception as exc:
            raise LLMError(f"LLM request failed: {type(exc).__name__}") from exc
        content = completion.choices[0].message.content
        if not content:
            raise LLMError("LLM returned an empty response")
        return content
