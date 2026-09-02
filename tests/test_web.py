"""The web UI is a second view of the same case files: the API must serve stored cases,
turn a 404 repo into a clean error, and let the page decide a budget pause."""

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from detective.agent import run_investigation
from detective.investigation import Investigation, STATUS_CONCLUDED
from detective.web import Hub, WebDecider, make_server

try:  # `python -m unittest discover -s tests` imports test modules top-level
    from test_agent_loop import INTAKE, VERBATIM, FakeGH, FakeLLM, FakeMsg, FakeToolCall
except ImportError:  # `python -m unittest tests.test_web`
    from tests.test_agent_loop import INTAKE, VERBATIM, FakeGH, FakeLLM, FakeMsg, FakeToolCall


class NotFoundGH:
    def get(self, path, params=None, accept=None):
        return {"ok": False, "error": "not_found", "message": "Not Found", "api_requests": 1}


class TestWebApi(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.hub = Hub(self.root, llm=None, gh_factory=NotFoundGH)
        self.httpd = make_server("127.0.0.1", 0, self.hub)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.status, r.read()

    def _post(self, path, body):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_index_and_empty_case_list(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"The Repo Detective", body)
        self.assertEqual(json.loads(self._get("/api/cases")[1]), [])

    def test_missing_repo_is_a_clean_400_before_any_llm_call(self):
        code, body = self._post("/api/investigate", {"url": "nobody/nothing"})
        self.assertEqual(code, 400)
        self.assertIn("404", body["error"])

    def test_unknown_case_is_404(self):
        self.assertEqual(self._post("/api/cases/nope/budget", {"granted": 5})[0], 404)
        self.assertEqual(self._post("/api/cases/nope/chat", {"message": "why?"})[0], 404)

    def test_stored_case_is_served_without_message_history(self):
        inv = Investigation.create(self.root, INTAKE, budget_initial=5)
        cases = json.loads(self._get("/api/cases")[1])
        self.assertEqual(cases[0]["full_name"], "acme/widget")
        detail = json.loads(self._get(f"/api/cases/{inv.slug}")[1])
        self.assertEqual(detail["status"], "in_progress")
        self.assertNotIn("messages", detail)
        # no live worker -> a budget decision is refused, not silently swallowed
        self.assertEqual(self._post(f"/api/cases/{inv.slug}/budget", {"granted": 3})[0], 409)


class StreamingLLM:
    """Classifier answers QUESTION; the grounded answer arrives in fragments, like a real endpoint."""
    fragments = ["The verdict ", "was adopt ", "because the log says so."]

    def complete(self, messages, tools=None, budget=None, max_tokens=8192, tool_choice=None):
        return FakeMsg(content="QUESTION")

    def stream(self, messages, max_tokens=8192):
        yield from self.fragments


class TestChatStreaming(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.inv = Investigation.create(self.root, INTAKE, budget_initial=5)
        self.hub = Hub(self.root, llm=StreamingLLM(), gh_factory=NotFoundGH)
        self.httpd = make_server("127.0.0.1", 0, self.hub)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _post_raw(self, path, body):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            return r.headers.get("Content-Type", ""), r.read().decode()

    def test_stream_endpoint_sends_the_answer_as_events(self):
        ctype, raw = self._post_raw(f"/api/cases/{self.inv.slug}/chat/stream", {"message": "why adopt?"})
        self.assertTrue(ctype.startswith("text/event-stream"))
        events = [json.loads(f[len("data: "):]) for f in raw.split("\n\n") if f.startswith("data: ")]
        kinds = [e["kind"] for e in events]
        self.assertEqual(kinds[0], "start")
        self.assertEqual(kinds[-1], "done")
        self.assertEqual([e["text"] for e in events if e["kind"] == "delta"], StreamingLLM.fragments)

    def test_one_shot_endpoint_returns_the_same_text_joined(self):
        ctype, raw = self._post_raw(f"/api/cases/{self.inv.slug}/chat", {"message": "why adopt?"})
        self.assertIn("json", ctype)
        self.assertEqual(json.loads(raw), {"kind": "answer", "text": "".join(StreamingLLM.fragments)})


class TestWebDecider(unittest.TestCase):
    def test_approval_from_the_page_extends_the_budget(self):
        inv = Investigation.create(Path(tempfile.mkdtemp()), INTAKE, budget_initial=1)
        decider = WebDecider()
        script = [
            FakeMsg(tool_calls=[FakeToolCall(1, "list_contributors",
                                             {"reasoning": "start", "owner": "acme", "repo": "widget"})]),
            # budget exhausted -> pause -> the page grants 3 -> the agent concludes
            FakeMsg(tool_calls=[FakeToolCall(2, "render_verdict", {
                "reasoning": "done", "decision": "adopt", "summary": "fine",
                "evidence": [{"claim": "solo dominates", "step_id": 1, "data_point": VERBATIM}]})]),
        ]
        threading.Timer(0.2, lambda: decider.resolve(3)).start()
        run_investigation(inv, FakeLLM(script), FakeGH(), decide=decider)

        ext = inv.state["budget"]["extensions"]
        self.assertEqual((ext[0]["granted"], ext[0]["decided_by"]), (3, "human (web)"))
        self.assertEqual(inv.status, STATUS_CONCLUDED)
        self.assertEqual(inv.budget_used(), 2)


if __name__ == "__main__":
    unittest.main()
