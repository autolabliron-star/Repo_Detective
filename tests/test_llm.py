"""The LLM client adapts to provider quirks without spending budget on them."""

import os
import unittest
from types import SimpleNamespace
from unittest import mock

import httpx
from openai import BadRequestError

from detective.llm import DEFAULT_MAX_TOKENS, REASONING_HEADROOM, REASONING_RETRY_HEADROOM, LLMClient

ENV = {"OPENAI_API_KEY": "sk-test", "OPENAI_MODEL": "test-model"}

TOOLS_NEED_NONE = ("Error code: 400 - Function tools with reasoning_effort are not supported for test-model in "
                   "/v1/chat/completions. To use function tools, use /v1/responses or set reasoning_effort to 'none'.")
UNKNOWN_PARAM = "Error code: 400 - Unrecognized request argument supplied: reasoning_effort"
TOOLS = [{"type": "function", "function": {"name": "get_repo", "parameters": {"type": "object"}}}]


def bad_request(text):
    resp = httpx.Response(400, request=httpx.Request("POST", "http://test/v1/chat/completions"))
    return BadRequestError(text, response=resp, body=None)


def reply(content="ok", finish_reason="stop", reasoning_tokens=0, tool_calls=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason=finish_reason,
                                 message=SimpleNamespace(content=content, tool_calls=tool_calls))],
        usage=SimpleNamespace(completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning_tokens)),
    )


class Budget:
    def __init__(self):
        self.counted = 0

    def remaining(self):
        return 30 - self.counted

    def count(self):
        self.counted += 1


class FakeProvider:
    """Records every request; `script` is a list of responses or exceptions, or a callable(kwargs)."""

    def __init__(self, script):
        self.script = script
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(dict(kwargs))
        item = self.script(kwargs) if callable(self.script) else self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_client(provider, extra_env=None):
    env = dict(ENV, **(extra_env or {}))
    with mock.patch.dict(os.environ, env, clear=True):
        llm = LLMClient()
    llm.client = SimpleNamespace(chat=SimpleNamespace(completions=provider))
    return llm


class TestReasoningEffort(unittest.TestCase):
    def test_tools_require_explicit_none_is_learned_once(self):
        provider = FakeProvider([bad_request(TOOLS_NEED_NONE), reply(), reply()])
        llm = make_client(provider)
        budget = Budget()

        msg = llm.complete([{"role": "user", "content": "hi"}], tools=TOOLS, budget=budget)

        self.assertEqual(msg.content, "ok")
        self.assertNotIn("reasoning_effort", provider.requests[0])
        self.assertEqual(provider.requests[1]["reasoning_effort"], "none")
        self.assertEqual(budget.counted, 1, "the adaptation round trip is not a budget unit")

        llm.complete([{"role": "user", "content": "again"}], tools=TOOLS, budget=budget)
        self.assertEqual(len(provider.requests), 3, "the learned value is sent up front next time")
        self.assertEqual(provider.requests[2]["reasoning_effort"], "none")
        self.assertEqual(budget.counted, 2)

    def test_configured_effort_switches_to_none_rather_than_being_dropped(self):
        provider = FakeProvider([bad_request(TOOLS_NEED_NONE), reply()])
        llm = make_client(provider, {"OPENAI_REASONING_EFFORT": "high"})

        llm.complete([{"role": "user", "content": "hi"}], tools=TOOLS)

        self.assertEqual([r.get("reasoning_effort") for r in provider.requests], ["high", "none"])

    def test_rejected_effort_is_dropped_without_tools(self):
        provider = FakeProvider([bad_request(UNKNOWN_PARAM), reply()])
        llm = make_client(provider, {"OPENAI_REASONING_EFFORT": "low"})
        budget = Budget()

        llm.complete([{"role": "user", "content": "hi"}], budget=budget)

        self.assertEqual(provider.requests[0]["reasoning_effort"], "low")
        self.assertNotIn("reasoning_effort", provider.requests[1])
        self.assertEqual(budget.counted, 1)

    def test_provider_that_rejects_every_effort_value_converges(self):
        """Non-reasoning model + configured effort + tools: low -> none -> dropped, then success. No loop."""
        def script(kwargs):
            if "reasoning_effort" in kwargs:
                return bad_request(UNKNOWN_PARAM)
            return reply()
        provider = FakeProvider(script)
        llm = make_client(provider, {"OPENAI_REASONING_EFFORT": "low"})
        budget = Budget()

        llm.complete([{"role": "user", "content": "hi"}], tools=TOOLS, budget=budget)

        self.assertEqual([r.get("reasoning_effort") for r in provider.requests], ["low", "none", None])
        self.assertEqual(budget.counted, 1)

    def test_unrelated_bad_request_propagates(self):
        provider = FakeProvider([bad_request("Error code: 400 - messages[0] is invalid")])
        llm = make_client(provider)
        with self.assertRaises(BadRequestError):
            llm.complete([{"role": "user", "content": "hi"}])


class TestOutputCap(unittest.TestCase):
    def test_default_cap_without_reasoning_has_no_headroom(self):
        provider = FakeProvider([reply(), reply()])
        llm = make_client(provider)
        llm.complete([{"role": "user", "content": "hi"}])
        llm.complete([{"role": "user", "content": "hi"}], max_tokens=800)
        self.assertEqual(provider.requests[0]["max_tokens"], DEFAULT_MAX_TOKENS)
        self.assertEqual(provider.requests[1]["max_tokens"], 800)

    def test_configured_reasoning_adds_headroom_to_tiny_caps(self):
        provider = FakeProvider([reply()])
        llm = make_client(provider, {"OPENAI_REASONING_EFFORT": "low"})
        llm.complete([{"role": "user", "content": "classify"}], max_tokens=8)
        self.assertEqual(provider.requests[0]["max_tokens"], 8 + REASONING_HEADROOM)

    def test_reasoning_learned_from_usage(self):
        provider = FakeProvider([reply(reasoning_tokens=300), reply(reasoning_tokens=300)])
        llm = make_client(provider)
        llm.complete([{"role": "user", "content": "hi"}], max_tokens=800)
        llm.complete([{"role": "user", "content": "hi"}], max_tokens=800)
        self.assertEqual(provider.requests[0]["max_tokens"], 800)
        self.assertEqual(provider.requests[1]["max_tokens"], 800 + REASONING_HEADROOM)

    def test_cap_eaten_by_reasoning_is_retried_once_uncounted(self):
        provider = FakeProvider([reply(content=None, finish_reason="length", reasoning_tokens=1000),
                                 reply(content="verdict", reasoning_tokens=900)])
        llm = make_client(provider, {"OPENAI_REASONING_EFFORT": "low"})
        budget = Budget()

        msg = llm.complete([{"role": "user", "content": "hi"}], budget=budget, max_tokens=8)

        self.assertEqual(msg.content, "verdict")
        self.assertEqual(len(provider.requests), 2)
        self.assertEqual(provider.requests[1]["max_tokens"], 8 + REASONING_RETRY_HEADROOM)
        self.assertEqual(budget.counted, 1)
        self.assertEqual(llm.last_finish_reason, "stop")

    def test_visible_truncation_is_not_retried(self):
        """A response with content but finish_reason=length is real output; the loop asks the model to compress."""
        provider = FakeProvider([reply(content="{partial", finish_reason="length", reasoning_tokens=50)])
        llm = make_client(provider, {"OPENAI_REASONING_EFFORT": "low"})
        budget = Budget()
        msg = llm.complete([{"role": "user", "content": "hi"}], budget=budget)
        self.assertEqual(msg.content, "{partial")
        self.assertEqual(llm.last_finish_reason, "length")
        self.assertEqual(budget.counted, 1)

    def test_max_tokens_renamed_when_rejected(self):
        provider = FakeProvider([bad_request("Error code: 400 - Unsupported parameter: 'max_tokens' is not supported "
                                             "with this model. Use 'max_completion_tokens' instead."), reply(), reply()])
        llm = make_client(provider)
        llm.complete([{"role": "user", "content": "hi"}], max_tokens=100)
        llm.complete([{"role": "user", "content": "hi"}], max_tokens=100)
        self.assertNotIn("max_tokens", provider.requests[1])
        self.assertEqual(provider.requests[1]["max_completion_tokens"], 100)
        self.assertEqual(provider.requests[2]["max_completion_tokens"], 100, "remembered across calls")


if __name__ == "__main__":
    unittest.main()
