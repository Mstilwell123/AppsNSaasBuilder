"""LLM provider abstraction for AppsNSaasBuilder scoring.

Supports two providers:
  - "emergent"  → Emergent's LlmChat integration (Claude Haiku 4.5) — the original
  - "openai"    → OpenAI API directly (GPT models)

Selection is via the LLM_PROVIDER env var (default: "emergent").

Each provider implements a single method: `async def complete(system, user) -> str`
that returns the raw text response from the model. The caller (_score_with_llm in
server.py) handles prompt construction, JSON extraction, and sanity clamping.

This keeps the scoring logic provider-agnostic — switching models is a config
change, not a code change.
"""

from __future__ import annotations

import os
import logging
import uuid
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract interface for LLM completion calls."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name (e.g. 'emergent', 'openai')."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """The model identifier being used (e.g. 'claude-haiku-4-5-20251001')."""

    @abstractmethod
    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send a system + user message to the LLM and return the raw text response."""


class EmergentProvider(LLMProvider):
    """Uses Emergent's LlmChat integration (original provider)."""

    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "emergent"

    @property
    def model_id(self) -> str:
        return self._model

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=self._api_key,
            session_id=f"score-{uuid.uuid4().hex[:12]}",
            system_message=system_prompt,
        ).with_model("anthropic", self._model)
        raw = await chat.send_message(UserMessage(text=user_prompt))
        return raw if isinstance(raw, str) else str(raw)


class OpenAIProvider(LLMProvider):
    """Uses the OpenAI API directly via httpx (no heavy SDK dependency)."""

    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model = model
        self._base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_id(self) -> str:
        return self._model

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        import httpx

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


def get_llm_provider() -> LLMProvider:
    """Factory: pick the LLM provider based on env vars.

    LLM_PROVIDER  — "emergent" (default) or "openai"
    EMERGENT_LLM_KEY  — Emergent API key (for emergent provider)
    SCORING_MODEL     — model ID for emergent (default: claude-haiku-4-5-20251001)
    OPENAI_API_KEY    — OpenAI API key (for openai provider)
    OPENAI_MODEL      — model ID for openai (default: gpt-4o-mini)
    """
    provider_name = os.environ.get("LLM_PROVIDER", "emergent").lower().strip()

    if provider_name == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is not set. "
                "Set it in backend/.env"
            )
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        logger.info("LLM provider: openai (model=%s)", model)
        return OpenAIProvider(api_key=api_key, model=model)

    # Default: Emergent
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        raise RuntimeError(
            "LLM_PROVIDER=emergent (default) but EMERGENT_LLM_KEY is not set. "
            "Set it in backend/.env, or set LLM_PROVIDER=openai with OPENAI_API_KEY."
        )
    model = os.environ.get("SCORING_MODEL", "claude-haiku-4-5-20251001")
    logger.info("LLM provider: emergent (model=%s)", model)
    return EmergentProvider(api_key=api_key, model=model)
