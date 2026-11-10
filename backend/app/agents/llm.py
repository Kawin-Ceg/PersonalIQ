"""LLM access (NVIDIA Nemotron through NVIDIA's OpenAI-compatible endpoint).

The LLM writes language (explanations, questions) and suggests structure from requests (validated
by code). It never decides prices, budgets,
rankings or payments. Every call has a deterministic fallback, so the workflow behaves the same
with no key, a slow network, or an error; the result just reads less naturally.
"""

import json
import logging
import re
from functools import lru_cache

from app.core.config import get_settings

log = logging.getLogger(__name__)


class LLM:
    def __init__(self) -> None:
        s = get_settings()
        self.model = s.llm_model
        self.provider = s.llm_provider
        self._client = None
        self.last_error: str | None = None  # shown in the status panel, e.g. "API key expired"
        if s.llm_api_key:
            from openai import OpenAI

            self._client = OpenAI(base_url=s.llm_base_url, api_key=s.llm_api_key, timeout=s.llm_timeout_seconds, max_retries=0)

    @property
    def available(self) -> bool:
        return self._client is not None

    SYSTEM = (
        "You are PersonalIQ, a careful shopping assistant. Use only the facts given. "
        "Never invent prices, products or numbers. Plain language, no markdown, no em dashes."
    )

    def _complete(self, system: str, user: str, max_tokens: int) -> str | None:
        """One chat call. Returns the text, or None on any problem (recorded in last_error)."""
        if not self.available:
            return None
        try:
            res = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.2,
                max_tokens=max_tokens,
                # Nemotron 3.x are reasoning models: left on, they spend the whole token budget
                # "thinking" and return no text. These are short tasks, so switch it off.
                extra_body={"reasoning": {"enabled": False}} if self.provider == "OpenRouter" else None,
            )
            text = (res.choices[0].message.content or "").strip()
            self.last_error = None if text else "Empty reply"
            return text or None
        except Exception as e:  # network, auth, rate limit: never fail the request because of the LLM
            log.warning("LLM call failed, using fallback: %s", e)
            self.last_error = _short_error(e)
            return None

    def write(self, instruction: str, facts: str, fallback: str, max_tokens: int = 160) -> tuple[str, bool]:
        """Rewrite `facts` per `instruction`. Returns (text, used_llm). Falls back on any problem."""
        text = self._complete(self.SYSTEM, f"{instruction}\n\nFacts:\n{facts}", max_tokens)
        return (text, True) if text else (fallback, False)

    def extract_json(self, instruction: str, text: str, max_tokens: int = 400) -> dict | None:
        """Ask for a JSON object. Returns the parsed dict, or None if unavailable or not valid JSON.
        The caller must validate every field: this is a suggestion, not a fact."""
        raw = self._complete(
            "You convert shopping requests into JSON. Reply with one JSON object only, no prose, no code fences.",
            f"{instruction}\n\nRequest:\n{text}",
            max_tokens,
        )
        if not raw:
            return None
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        try:
            data = json.loads(match.group(0)) if match else None
        except json.JSONDecodeError:
            data = None
        if not isinstance(data, dict):
            self.last_error = "Reply was not JSON"
            return None
        return data


def _short_error(e: Exception) -> str:
    status = getattr(e, "status_code", None)
    msg = str(getattr(e, "message", "") or e)
    if status == 401:
        return "Key expired or invalid" if "expired" in msg.lower() else "Key invalid"
    if status == 429:
        return "Rate limited"
    if status:
        return f"Error {status}"
    return "Unreachable" if "timeout" not in msg.lower() else "Timed out"


@lru_cache
def get_llm() -> LLM:
    return LLM()
