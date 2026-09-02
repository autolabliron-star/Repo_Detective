"""Web UI — `docker compose up` serves it at http://localhost:8000.

Standard library only (http.server + json): no new dependency, one self-contained
HTML file, works offline. The page reads the same state.json the CLI writes (polling
while a case is live), so the browser and the terminal are two views of one
investigation. A budget pause becomes an Approve / Deny panel: the agent's thread
blocks on a WebDecider until the page answers (or 30 minutes pass → denied, so a
forgotten tab can never hang a run forever).
"""

from __future__ import annotations

import json
import re
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import chat as chat_mod
from .agent import run_investigation
from .github_client import GitHubClient
from .intake import run_intake
from .investigation import Investigation, STATUS_CONCLUDED, STATUS_NO_VERDICT

STATIC_DIR = Path(__file__).parent / "static"
DECISION_TIMEOUT_S = 1800
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


class WebDecider:
    """The human-in-the-loop channel for one live case: run_investigation calls it at a budget
    pause; it blocks until the page posts a decision."""

    label = "human (web)"

    def __init__(self):
        self._event = threading.Event()
        self._granted = 0

    def __call__(self, inv, requested: int, pitch: dict | None) -> int:
        self._event.clear()
        if not self._event.wait(DECISION_TIMEOUT_S):
            return 0
        return self._granted

    def resolve(self, granted: int) -> None:
        self._granted = max(0, int(granted))
        self._event.set()


class Hub:
    """Owns the live cases: one worker thread per running investigation or re-task."""

    def __init__(self, root: Path, llm, gh_factory=None, default_budget: int = 30):
        self.root = Path(root)
        self.llm = llm
        self.gh_factory = gh_factory or (lambda: GitHubClient(cache_dir=self.root / ".httpcache"))
        self.default_budget = default_budget
        self.running: dict[str, dict] = {}
        self.errors: dict[str, str] = {}
        self.lock = threading.Lock()

    # ------------------------------ workers ------------------------------ #

    def _run(self, slug: str, target) -> None:
        try:
            target()
        except SystemExit as exc:  # fail-fast paths (bad key, unknown model) end the thread, not the server
            self.errors[slug] = str(exc) or "stopped"
        except Exception as exc:
            self.errors[slug] = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
        finally:
            with self.lock:
                self.running.pop(slug, None)

    def _launch(self, slug: str, kind: str, target) -> bool:
        decider = WebDecider()
        with self.lock:
            if slug in self.running:
                return False
            self.running[slug] = {"decider": decider, "kind": kind}
        self.errors.pop(slug, None)
        threading.Thread(target=self._run, args=(slug, lambda: target(decider)),
                         daemon=True, name=f"{kind}:{slug}").start()
        return True

    # ------------------------------ actions ------------------------------ #

    def start_investigation(self, url: str, budget: int | None = None, fresh: bool = False):
        """Returns (slug, None) or (None, error). Intake runs synchronously so a 404 is a clean 400."""
        gh = self.gh_factory()
        intake, fatal = run_intake(gh, url)
        if fatal:
            return None, fatal
        existing = Investigation.find(self.root, intake["canonical_full_name"])
        if existing and existing.slug in self.running:
            return existing.slug, None  # already live — just open it
        if existing and not fresh:
            if existing.status in (STATUS_CONCLUDED, STATUS_NO_VERDICT):
                return existing.slug, None  # open the stored case; the page offers "start over"
            inv = existing  # interrupted earlier — resume
        else:
            inv = Investigation.create(self.root, intake, budget_initial=budget or self.default_budget)
        self._launch(inv.slug, "investigate", lambda decider: run_investigation(inv, self.llm, gh, decide=decider))
        return inv.slug, None

    def decide(self, slug: str, granted: int) -> bool:
        with self.lock:
            entry = self.running.get(slug)
        if not entry:
            return False
        entry["decider"].resolve(granted)
        return True

    def chat(self, slug: str, message: str) -> dict | None:
        inv = Investigation.find(self.root, slug)
        if not inv:
            return None
        if chat_mod.classify(self.llm, message) == "retask":
            if slug in self.running:
                return {"kind": "busy", "text": "The agent is still working on this case — wait for it to finish, then re-task."}
            remaining = inv.budget_remaining()
            gh = self.gh_factory()
            self._launch(inv.slug, "retask",
                         lambda decider: chat_mod.retask(inv, self.llm, gh, message, decide=decider))
            return {"kind": "retask", "text": f"Re-tasked — the agent is resuming with {remaining} LLM calls remaining. "
                                              "Watch the log; a new verdict version appears when it concludes."}
        return {"kind": "answer", "text": _ANSI.sub("", chat_mod.answer_question(inv, self.llm, message))}

    # ------------------------------- views ------------------------------- #

    def case_summary(self, inv: Investigation) -> dict:
        v = inv.latest_verdict()
        return {
            "full_name": inv.full_name, "slug": inv.slug, "status": inv.status,
            "verdict": v["decision"] if v else None, "confidence": v.get("confidence") if v else None,
            "version": v["version"] if v else 0,
            "budget_used": inv.budget_used(), "budget_granted": inv.budget_granted(),
            "running": inv.slug in self.running, "error": self.errors.get(inv.slug),
            "investigated_at": inv.state["repo"].get("investigated_at"),
        }

    def case_detail(self, inv: Investigation) -> dict:
        d = self.case_summary(inv)
        d.update({
            "intake": inv.state["intake"], "budget": inv.state["budget"], "log": inv.log,
            "verdicts": inv.state["verdicts"],
            "pending_pitch": inv.state.get("pending_pitch") if inv.status == "paused_awaiting_budget" else None,
        })
        return d  # never the raw message history — the log is the record


class Handler(BaseHTTPRequestHandler):
    hub: Hub  # bound per server in make_server

    def log_message(self, fmt, *args):  # keep the terminal for the investigation stream
        pass

    def _send(self, code: int, body, ctype: str = "application/json; charset=utf-8") -> None:
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return None
        return body if isinstance(body, dict) else None

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/":
            return self._send(200, (STATIC_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/api/cases":
            cases = [self.hub.case_summary(i) for i in Investigation.list_all(self.hub.root)]
            cases.sort(key=lambda c: c.get("investigated_at") or "", reverse=True)
            return self._send(200, cases)
        m = re.match(r"^/api/cases/([^/]+)(/report)?$", path)
        if m:
            inv = Investigation.find(self.hub.root, m.group(1))
            if not inv:
                return self._send(404, {"error": "no such case"})
            if m.group(2):
                report = inv.dir / "report.md"
                return self._send(200, report.read_bytes() if report.exists() else b"(no report rendered yet)",
                                  "text/markdown; charset=utf-8")
            return self._send(200, self.hub.case_detail(inv))
        self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        body = self._json_body()
        if body is None:
            return self._send(400, {"error": "request body must be a JSON object"})
        if path == "/api/investigate":
            url = (body.get("url") or "").strip()
            if not url:
                return self._send(400, {"error": "url is required"})
            try:
                budget = int(body.get("budget") or 0) or None
            except (TypeError, ValueError):
                return self._send(400, {"error": "budget must be a number"})
            slug, err = self.hub.start_investigation(url, budget, bool(body.get("fresh")))
            return self._send(400, {"error": err}) if err else self._send(200, {"slug": slug})
        m = re.match(r"^/api/cases/([^/]+)/(budget|chat)$", path)
        if m:
            inv = Investigation.find(self.hub.root, m.group(1))
            if not inv:
                return self._send(404, {"error": "no such case"})
            if m.group(2) == "budget":
                try:
                    granted = int(body.get("granted", 0))
                except (TypeError, ValueError):
                    return self._send(400, {"error": "granted must be a number"})
                if self.hub.decide(inv.slug, granted):
                    return self._send(200, {"ok": True, "granted": granted})
                return self._send(409, {"error": "this case has no pending budget decision"})
            message = (body.get("message") or "").strip()
            if not message:
                return self._send(400, {"error": "message is required"})
            return self._send(200, self.hub.chat(inv.slug, message))
        self._send(404, {"error": "not found"})


def make_server(host: str, port: int, hub: Hub) -> ThreadingHTTPServer:
    bound = type("BoundHandler", (Handler,), {"hub": hub})
    ThreadingHTTPServer.allow_reuse_address = True
    return ThreadingHTTPServer((host, port), bound)


def serve(host: str, port: int, root: Path, llm, default_budget: int = 30) -> int:
    hub = Hub(root, llm, default_budget=default_budget)
    httpd = make_server(host, port, hub)
    shown = "localhost" if host in ("0.0.0.0", "") else host
    print(f"🔍 The Repo Detective — web UI at http://{shown}:{port}  (Ctrl-C to stop)")
    print("   Investigations stream here in the terminal too; the page polls the same case files.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
