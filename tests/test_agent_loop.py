"""End-to-end agent loop with a scripted fake LLM and fake GitHub:
exercises tool dispatch + logging, evidence-validation rejection, the
budget-exhaustion pause with non-interactive auto-deny (1 wrap-up call),
and report rendering — no network, no API key."""

import json
import tempfile
import unittest
from pathlib import Path

from detective.agent import run_investigation
from detective.investigation import Investigation, STATUS_CONCLUDED, STATUS_NO_VERDICT
from detective.llm import check_budget


class FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = json.dumps(arguments)


class FakeToolCall:
    def __init__(self, i, name, arguments, raw=None):
        self.id = f"call_{i}"
        self.function = FakeFunction(name, arguments)
        if raw is not None:  # simulate a provider handing back cut-off JSON
            self.function.arguments = raw


class FakeMsg:
    def __init__(self, tool_calls=None, content=None, finish_reason="tool_calls"):
        self.content = content
        self.tool_calls = tool_calls
        self.finish_reason = finish_reason


class FakeLLM:
    def __init__(self, script):
        self.script = list(script)
        self.last_finish_reason = None

    def complete(self, messages, tools=None, budget=None, max_tokens=4096, tool_choice=None):
        check_budget(budget)
        self.last_tools = tools
        self.last_tool_choice = tool_choice
        msg = self.script.pop(0)
        if budget is not None:
            budget.count()
        self.last_finish_reason = msg.finish_reason
        return msg


class FakeGH:
    """Canned GitHub responses; enough for get_repo + list_contributors."""

    def get(self, path, params=None, accept=None):
        if path.endswith("/contributors"):
            return {"ok": True, "api_requests": 1, "data": [
                {"login": "solo", "contributions": 95},
                {"login": "other", "contributions": 5},
            ]}
        if path.startswith("/repos/"):
            return {"ok": True, "api_requests": 1, "data": {
                "full_name": "acme/widget", "description": "a widget",
                "stargazers_count": 100, "forks_count": 5, "open_issues_count": 3,
                "created_at": "2020-01-01T00:00:00Z", "pushed_at": "2026-08-01T00:00:00Z",
                "default_branch": "main", "license": {"spdx_id": "MIT"},
                "language": "Python", "size": 10, "archived": False, "disabled": False, "fork": False,
            }}
        return {"ok": False, "api_requests": 1, "error": "not_found", "message": "nope"}


INTAKE = {"input_url": "acme/widget", "canonical_full_name": "acme/widget",
          "description": "a widget", "stars": 100, "forks": 5, "open_issues_and_prs": 3,
          "language": "Python", "license": "MIT", "created_at": "2020-01-01T00:00:00Z",
          "pushed_at": "2026-08-01T00:00:00Z", "release_note": "no GitHub releases",
          "top_contributors": [], "warnings": []}


def make_inv(budget):
    return Investigation.create(Path(tempfile.mkdtemp()), INTAKE, budget_initial=budget)


VERBATIM = "solo: 95 commits (95.0%)"  # appears verbatim in list_contributors' observation


class TestAgentLoop(unittest.TestCase):
    def test_fabricated_evidence_rejected_then_verbatim_accepted(self):
        inv = make_inv(budget=5)
        script = [
            FakeMsg(tool_calls=[
                FakeToolCall(1, "get_repo", {"reasoning": "size it up", "owner": "acme", "repo": "widget"}),
                FakeToolCall(2, "list_contributors", {"reasoning": "who writes this?", "owner": "acme", "repo": "widget"}),
            ]),
            FakeMsg(tool_calls=[FakeToolCall(3, "render_verdict", {
                "reasoning": "done", "decision": "reject", "summary": "folklore",
                "evidence": [{"claim": "known malware incident", "step_id": 2,
                              "data_point": "shipped destructive protestware in 2022"}],
            })]),
            FakeMsg(tool_calls=[FakeToolCall(4, "render_verdict", {
                "reasoning": "re-cited", "decision": "adopt_with_conditions", "summary": "solo maintainer",
                "evidence": [{"claim": "one person wrote 95% of the code", "step_id": 2, "data_point": VERBATIM}],
                "conditions": ["monitor bus factor"],
            })]),
        ]
        run_investigation(inv, FakeLLM(script), FakeGH())

        self.assertEqual(inv.status, STATUS_CONCLUDED)
        v = inv.latest_verdict()
        self.assertEqual(v["decision"], "adopt_with_conditions")
        self.assertTrue(v["validation_passed"])
        self.assertTrue(v["evidence"][0]["verified"])
        # the fabricated attempt is itself a first-class log step
        failed = [e for e in inv.log if e["tool"] == "render_verdict" and e["error"] == "validation_failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(inv.budget_used(), 3)
        report = (inv.dir / "report.md").read_text()
        self.assertIn("ADOPT WITH CONDITIONS", report)
        self.assertIn(VERBATIM, report)

    def test_budget_exhaustion_pauses_then_wrapup_verdict(self):
        inv = make_inv(budget=1)
        script = [
            FakeMsg(tool_calls=[FakeToolCall(1, "list_contributors",
                                             {"reasoning": "start", "owner": "acme", "repo": "widget"})]),
            # budget now exhausted -> pause -> auto-deny (non-interactive) -> 1 wrap-up call:
            FakeMsg(tool_calls=[FakeToolCall(2, "render_verdict", {
                "reasoning": "forced wrap-up", "decision": "adopt", "summary": "fine",
                "evidence": [{"claim": "solo dominates", "step_id": 1, "data_point": VERBATIM}],
                "unverified_notes": ["ran out of budget before checking issues"],
            })]),
        ]
        run_investigation(inv, FakeLLM(script), FakeGH())

        self.assertEqual(inv.status, STATUS_CONCLUDED)
        ext = inv.state["budget"]["extensions"]
        self.assertEqual(len(ext), 1)
        self.assertEqual(ext[0]["granted"], 1)  # denial grants exactly one wrap-up call
        self.assertEqual(inv.budget_used(), 2)
        self.assertEqual(inv.budget_remaining(), 0)
        self.assertEqual(inv.latest_verdict()["decision"], "adopt")

    def test_no_budget_creep_when_agent_ignores_wrapup(self):
        """Regression: a denial grants ONE wrap-up call. An agent that tries to keep
        investigating must be hard-stopped — the budget must not creep 30->31->32..."""
        inv = make_inv(budget=1)
        llm = FakeLLM([
            FakeMsg(tool_calls=[FakeToolCall(1, "list_contributors",
                                             {"reasoning": "start", "owner": "acme", "repo": "widget"})]),
            # non-compliant: spends the wrap-up call trying to investigate again
            FakeMsg(tool_calls=[FakeToolCall(2, "get_repo",
                                             {"reasoning": "one more look", "owner": "acme", "repo": "widget"})]),
        ])
        run_investigation(inv, llm, FakeGH())

        self.assertEqual(inv.status, STATUS_NO_VERDICT)
        self.assertEqual(len(inv.state["budget"]["extensions"]), 1)  # exactly one wrap-up, never more
        self.assertEqual(inv.budget_used(), 2)
        self.assertEqual(inv.budget_remaining(), 0)
        # the wrap-up call mounted only render_verdict, forced
        self.assertEqual([t["function"]["name"] for t in llm.last_tools], ["render_verdict"])
        self.assertEqual(llm.last_tool_choice["function"]["name"], "render_verdict")
        self.assertIn("none rendered", (inv.dir / "report.md").read_text())

    def test_truncated_verdict_is_logged_and_agent_told_to_compress(self):
        """Regression from the first live run: a verdict cut off by the output cap came back as
        'bad arguments, re-issue' and the model re-issued the same oversized verdict 8 times."""
        inv = make_inv(budget=5)
        cut_off = ('{"reasoning": "wrapping up the case", "decision": "adopt", "summary": "fine", '
                   '"evidence": [{"claim": "x", "step_id": 1, "data_point": "solo: 95 com')
        script = [
            FakeMsg(tool_calls=[FakeToolCall(1, "list_contributors",
                                             {"reasoning": "start", "owner": "acme", "repo": "widget"})]),
            FakeMsg(tool_calls=[FakeToolCall(2, "render_verdict", {}, raw=cut_off)], finish_reason="length"),
            FakeMsg(tool_calls=[FakeToolCall(3, "render_verdict", {
                "reasoning": "compact retry", "decision": "adopt", "summary": "fine",
                "evidence": [{"claim": "solo dominates", "step_id": 1, "data_point": VERBATIM}],
            })]),
        ]
        run_investigation(inv, FakeLLM(script), FakeGH())

        self.assertEqual(inv.status, STATUS_CONCLUDED)
        truncated = [e for e in inv.log if e["error"] == "truncated"]
        self.assertEqual(len(truncated), 1)
        self.assertEqual(truncated[0]["reasoning"], "wrapping up the case")  # salvaged from the broken JSON
        feedback = [m for m in inv.messages if m["role"] == "tool" and "truncated" in m["content"]]
        self.assertIn("COMPACTLY", feedback[0]["content"])
        self.assertEqual(inv.budget_used(), 3)
        # steps remember which LLM call produced them
        self.assertEqual([e["call"] for e in inv.log], [1, 2, 3])
        self.assertIn("LLM call 2", (inv.dir / "report.md").read_text())

    def test_resume_repairs_interrupted_history(self):
        inv = make_inv(budget=3)
        # simulate dying between the assistant message and its tool results
        inv.messages.append({"role": "system", "content": "x"})
        inv.messages.append({"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_9", "type": "function",
             "function": {"name": "get_repo", "arguments": "{}"}}]})
        inv.save()
        from detective.agent import repair_messages
        repair_messages(inv)
        self.assertEqual(inv.messages[-1]["role"], "tool")
        self.assertIn("interrupted", inv.messages[-1]["content"])


if __name__ == "__main__":
    unittest.main()
