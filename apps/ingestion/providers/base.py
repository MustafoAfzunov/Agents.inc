"""Abstract LLM provider.

The extractor only depends on this small interface, which makes it easy to
swap OpenAI for Claude/Gemini/Ollama later, or to plug in a deterministic
mock for tests without monkey-patching.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Contract every concrete LLM provider must implement."""

    name: str = "base"

    @abstractmethod
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return the model's response as a *raw* JSON string.

        Implementations should request JSON-mode output where available; the
        extractor is still responsible for parsing and validating it.
        """
