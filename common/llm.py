"""A tiny LLM client that speaks the OpenAI chat-completions format.

Backend selection (first match wins):
  1. OPENAI_API_KEY               -> OpenAI (or any compatible server via OPENAI_BASE_URL)
  2. GROQ_API_KEY                 -> Groq (llama-3.3-70b-versatile)
  3. GOOGLE_API_KEY/GEMINI_API_KEY -> Gemini's OpenAI-compatible endpoint
  4. nothing set                  -> Pollinations, a free keyless endpoint

Every backend accepts the same request body, so the rest of the lab never
needs to care which one is in use.
"""

from __future__ import annotations

import json
import os
import time

import httpx

TIMEOUT_SECONDS = 90
MAX_ATTEMPTS = 3

POLLINATIONS_URL = "https://text.pollinations.ai/openai"


class LLMError(Exception):
    """Raised when the LLM backend cannot give us a usable answer."""


class LLMClient:
    def __init__(self, model: str | None = None):
        # Work out which backend to use from the environment.
        if os.getenv("OPENAI_API_KEY"):
            self.backend = "openai"
            base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            self.url = base.rstrip("/") + "/chat/completions"
            self.api_key = os.getenv("OPENAI_API_KEY")
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        elif os.getenv("GROQ_API_KEY"):
            self.backend = "groq"
            self.url = "https://api.groq.com/openai/v1/chat/completions"
            self.api_key = os.getenv("GROQ_API_KEY")
            self.model = model or "llama-3.3-70b-versatile"
        elif os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
            self.backend = "gemini"
            self.url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            self.model = model or "gemini-2.0-flash"
        else:
            self.backend = "pollinations"
            self.url = POLLINATIONS_URL
            self.api_key = None
            self.model = model or "openai"

        # Some endpoints reject temperature; we drop it after the first complaint.
        self._send_temperature = True

    def describe(self) -> str:
        """Human-readable summary, e.g. for a UI caption or a CLI banner."""
        if self.backend == "pollinations":
            return f"pollinations:{self.model} (keyless, gpt-oss-20b)"
        return f"{self.backend}:{self.model}"

    # ------------------------------------------------------------------
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Send one chat-completions request and return the assistant message.

        The returned dict always has the same shape:
            {"role": "assistant", "content": str | None,
             "tool_calls": [...], "reasoning": str | None}
        """
        body: dict = {"model": self.model, "messages": messages}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data = self._post_with_retries(body, headers)

        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            raise LLMError(f"Unexpected response from {self.backend}: {str(data)[:300]}")
        return _normalise(message)

    def _post_with_retries(self, body: dict, headers: dict) -> dict:
        last_error = "unknown error"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            payload = dict(body)
            if self._send_temperature:
                payload["temperature"] = 0
            try:
                resp = httpx.post(self.url, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
            except httpx.HTTPError as e:
                last_error = f"network error: {e!r}"
            else:
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except ValueError:
                        last_error = f"invalid JSON: {resp.text[:200]}"
                elif resp.status_code == 400 and self._send_temperature and "temperature" in resp.text.lower():
                    # This model does not like temperature=0 -> retry without it straight away.
                    self._send_temperature = False
                    continue
                elif resp.status_code == 429 or resp.status_code >= 500:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                else:
                    # 4xx errors (bad key, bad request) will not fix themselves.
                    raise LLMError(f"{self.backend} returned HTTP {resp.status_code}: {resp.text[:300]}")

            if attempt < MAX_ATTEMPTS:
                time.sleep(2 ** attempt)  # 2s, 4s backoff
        raise LLMError(f"{self.backend} failed after {MAX_ATTEMPTS} attempts ({last_error})")


def _normalise(message: dict) -> dict:
    """Coerce a provider's assistant message into one predictable shape."""
    tool_calls = []
    for i, tc in enumerate(message.get("tool_calls") or []):
        fn = tc.get("function") or {}
        args = fn.get("arguments", "{}")
        if not isinstance(args, str):  # a few providers send a dict
            args = json.dumps(args)
        tool_calls.append({
            "id": tc.get("id") or f"call_{i}",
            "type": "function",
            "function": {"name": fn.get("name", ""), "arguments": args or "{}"},
        })

    return {
        "role": "assistant",
        "content": message.get("content") or None,
        "tool_calls": tool_calls,
        "reasoning": message.get("reasoning") or message.get("reasoning_content") or None,
    }
