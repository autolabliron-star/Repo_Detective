"""OpenAI-compatible LLM client — the single choke point for the call budget.

Every counted request passes through complete(budget=...): the budget is
checked before the request and incremented (and persisted, by the budget
object) after a successful response. One successful chat completion = one
budget unit, however many parallel tool calls it carries. Transport retries
don't count. Chat Q&A passes budget=None — uncounted by design.

Provider-agnostic: reads OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL, and
adapts when a provider rejects temperature or max_tokens.
"""

from __future__ import annotations

import os
import time

from openai import (
    APIConnectionError,
    APIStatusError,
    BadRequestError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)


class BudgetExhausted(Exception):
    """Raised before any API request when the investigation budget is spent."""


def check_budget(budget) -> None:
    if budget is not None and budget.remaining() <= 0:
        raise BudgetExhausted()


class LLMClient:
    def __init__(self):
        key = os.environ.get("OPENAI_API_KEY")
        model = os.environ.get("OPENAI_MODEL")
        missing = [name for name, val in (("OPENAI_API_KEY", key), ("OPENAI_MODEL", model)) if not val]
        if missing:
            raise SystemExit(f"Missing required environment variable(s): {', '.join(missing)}. "
                             "Copy .env.example to .env and fill them in.")
        base = (os.environ.get("OPENAI_BASE_URL") or "").rstrip("/") or None
        self.model = model
        self.client = OpenAI(api_key=key, base_url=base)
        self._supports_temperature = True
        self._max_tokens_param = "max_tokens"

    def complete(self, messages: list[dict], tools: list[dict] | None = None,
                 budget=None, max_tokens: int = 1024):
        """Returns the assistant message. `budget` is a duck-typed object with
        .remaining() and .count() (the Investigation) — None means uncounted."""
        check_budget(budget)

        kwargs: dict = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if self._supports_temperature:
            kwargs["temperature"] = 0.2
        kwargs[self._max_tokens_param] = max_tokens

        last_exc: Exception | None = None
        attempt = 0
        while attempt < 4:
            try:
                resp = self.client.chat.completions.create(**kwargs)
                if budget is not None:
                    budget.count()
                return resp.choices[0].message
            except BadRequestError as exc:
                text = str(exc)
                # Some providers/models reject these params; adapt once and retry (not counted as an attempt).
                if "temperature" in text and self._supports_temperature:
                    self._supports_temperature = False
                    kwargs.pop("temperature", None)
                    continue
                if "max_tokens" in text and self._max_tokens_param == "max_tokens":
                    self._max_tokens_param = "max_completion_tokens"
                    kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
                    continue
                raise
            except (RateLimitError, APIConnectionError, InternalServerError, APIStatusError) as exc:
                last_exc = exc
                attempt += 1
                if attempt < 4:
                    time.sleep(2 ** attempt)
        raise SystemExit(f"LLM provider unreachable after retries: {last_exc}")
