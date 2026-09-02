"""OpenAI-compatible LLM client — the single choke point for the call budget.

Every counted request passes through complete(budget=...): the budget is
checked before the request and incremented (and persisted, by the budget
object) after a successful response. One successful chat completion = one
budget unit, however many parallel tool calls it carries. Transport retries
don't count. Chat Q&A passes budget=None — uncounted by design.

Provider-agnostic: reads OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL, plus
an optional OPENAI_REASONING_EFFORT for reasoning models, and adapts when a
provider rejects temperature, max_tokens, a forced tool_choice or
reasoning_effort.

Output cap: the verdict JSON is the longest thing the agent ever emits (a
summary plus verbatim evidence quotes). A 1024-token cap silently truncated it
in the first live run and the retry loop looked exactly like budget creep — so
the default is generous, and last_finish_reason exposes "length" so the loop
can tell the model to compress instead of blindly re-issuing. Reasoning models
spend hidden reasoning tokens out of the same cap: once a model is known to
reason (OPENAI_REASONING_EFFORT set, or reasoning tokens reported in usage)
every cap gets headroom, and a response whose cap was consumed entirely by
reasoning — nothing visible came back — is retried once with more room. That
retry is one HTTP request, not a second budget unit.

Endpoint quirk learned live: OpenAI's chat/completions refuses function tools
for some reasoning models (gpt-5.6-terra) unless reasoning_effort is an
explicit "none" — even when no effort was sent. The client reads that from
the 400, switches to "none" for the rest of the process and retries, so a run
survives a model switch with no configuration. Adaptations are uncounted.
"""

from __future__ import annotations

import os
import sys
import time

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

DEFAULT_MAX_TOKENS = 8192
REASONING_HEADROOM = 1024        # hidden reasoning tokens ride on top of every visible-output cap
REASONING_RETRY_HEADROOM = 4096  # when reasoning alone consumed the cap, the one retry gets this much


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
        if key == "sk-your-key-here":
            raise SystemExit("OPENAI_API_KEY is still the example value from .env.example — paste your real key into .env.")
        base = (os.environ.get("OPENAI_BASE_URL") or "").rstrip("/") or None
        self.model = model
        self.client = OpenAI(api_key=key, base_url=base)
        self._supports_temperature = True
        self._max_tokens_param = "max_tokens"
        self._reasoning_effort = os.environ.get("OPENAI_REASONING_EFFORT") or None
        # Whether hidden reasoning tokens share the output cap; also flips on when usage reports them.
        self._reasons = self._reasoning_effort not in (None, "none")
        self.last_finish_reason: str | None = None

    def complete(self, messages: list[dict], tools: list[dict] | None = None,
                 budget=None, max_tokens: int = DEFAULT_MAX_TOKENS, tool_choice=None):
        """Returns the assistant message. `budget` is a duck-typed object with
        .remaining() and .count() (the Investigation) — None means uncounted.
        `tool_choice` may force a specific function (the wrap-up call).
        `max_tokens` is the visible-output cap; reasoning models get headroom on top."""
        check_budget(budget)

        kwargs: dict = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"
        if self._supports_temperature:
            kwargs["temperature"] = 0.2
        if self._reasoning_effort:
            kwargs["reasoning_effort"] = self._reasoning_effort
        kwargs[self._max_tokens_param] = self._cap(max_tokens)

        last_exc: Exception | None = None
        attempt = 0
        cap_retried = False
        tried_effort = {kwargs.get("reasoning_effort")}  # values already refused — never loop between two 400s
        while attempt < 4:
            try:
                resp = self.client.chat.completions.create(**kwargs)
                choice = resp.choices[0]
                if (self._saw_reasoning(resp) and not cap_retried and choice.finish_reason == "length"
                        and not choice.message.content and not choice.message.tool_calls):
                    # Reasoning ate the whole cap before a single visible token. Nothing usable came back,
                    # so this is not a budget unit — retry once with room to think.
                    cap_retried = True
                    kwargs[self._max_tokens_param] = max_tokens + REASONING_RETRY_HEADROOM
                    continue
                if budget is not None:
                    budget.count()
                self.last_finish_reason = choice.finish_reason  # "length" == output was truncated
                return choice.message
            except BadRequestError as exc:
                text = str(exc)
                # Some providers/models reject these params; adapt once and retry (not counted as an attempt).
                if "reasoning_effort" in text:
                    current = kwargs.get("reasoning_effort")
                    if kwargs.get("tools") and current != "none" and "none" not in tried_effort:
                        # Tools on chat/completions need an explicit 'none' — checked before the drop branch,
                        # otherwise a configured effort gets dropped and the very next attempt fails the same way.
                        was = f" (was {current!r})" if current else ""
                        print(f"note: '{self.model}' only accepts tools with reasoning_effort='none' on this "
                              f"endpoint{was} — continuing with 'none'.", file=sys.stderr)
                        self._reasoning_effort = "none"
                        self._reasons = False
                        kwargs["reasoning_effort"] = "none"
                        tried_effort.add("none")
                        continue
                    if current is not None and None not in tried_effort:
                        print(f"note: the provider rejected reasoning_effort={current!r} for '{self.model}' — "
                              "continuing without it.", file=sys.stderr)
                        self._reasoning_effort = None
                        kwargs.pop("reasoning_effort", None)
                        tried_effort.add(None)
                        continue
                if "temperature" in text and self._supports_temperature:
                    self._supports_temperature = False
                    kwargs.pop("temperature", None)
                    continue
                if "max_tokens" in text and self._max_tokens_param == "max_tokens":
                    self._max_tokens_param = "max_completion_tokens"
                    kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
                    continue
                if "tool_choice" in text and kwargs.get("tool_choice") not in (None, "auto"):
                    kwargs["tool_choice"] = "auto"  # provider doesn't support forced choice
                    continue
                raise
            except AuthenticationError:
                raise SystemExit("The LLM provider rejected the API key (401) — check OPENAI_API_KEY in .env.")
            except PermissionDeniedError as exc:
                raise SystemExit(f"The LLM provider denied access (403) — check the key's permissions. {exc}")
            except NotFoundError:
                raise SystemExit(f"The LLM provider doesn't serve model '{self.model}' (404) — check OPENAI_MODEL "
                                 "(and that OPENAI_BASE_URL points at the right endpoint).")
            except (RateLimitError, APIConnectionError, InternalServerError, APIStatusError) as exc:
                last_exc = exc
                attempt += 1
                if attempt < 4:
                    time.sleep(2 ** attempt)
        raise SystemExit(f"LLM provider unreachable after retries: {last_exc}")

    def stream(self, messages: list[dict], max_tokens: int = DEFAULT_MAX_TOKENS):
        """Yield the assistant's visible text as it is generated — the chat's Q&A path, so it is
        uncounted and mounts no tools. If the endpoint refuses to stream (or fails before the first
        token), falls back to one complete() response, which carries the provider adaptations."""
        kwargs: dict = {"model": self.model, "messages": messages, "stream": True}
        if self._supports_temperature:
            kwargs["temperature"] = 0.2
        if self._reasoning_effort:
            kwargs["reasoning_effort"] = self._reasoning_effort
        kwargs[self._max_tokens_param] = self._cap(max_tokens)
        got_any = False
        try:
            finish = None
            for chunk in self.client.chat.completions.create(**kwargs):
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                choice = choices[0]
                delta = getattr(choice, "delta", None)
                text = getattr(delta, "content", None) if delta is not None else None
                if text:
                    got_any = True
                    yield text
                if getattr(choice, "finish_reason", None):
                    finish = choice.finish_reason
            if got_any:
                self.last_finish_reason = finish
                return
        except Exception:
            if got_any:  # the stream broke mid-answer — don't restart and duplicate what was shown
                raise
        yield self.complete(messages, max_tokens=max_tokens).content or ""

    # ------------------------------------------------------------------ #

    def _cap(self, max_tokens: int) -> int:
        return max_tokens + REASONING_HEADROOM if self._reasons else max_tokens

    def _saw_reasoning(self, resp) -> bool:
        """Learn from usage whether this model reasons (reasoning_tokens > 0), even without OPENAI_REASONING_EFFORT."""
        details = getattr(getattr(resp, "usage", None), "completion_tokens_details", None)
        if (getattr(details, "reasoning_tokens", None) or 0) > 0:
            self._reasons = True
        return self._reasons
