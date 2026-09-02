"""Tool registry: OpenAI function-calling schemas + dispatch.

Conventions that make the whole design work:
- Every tool requires a `reasoning` argument — the detective's case notes.
  It costs zero extra LLM calls and becomes the investigation log's narrative.
- Every repo tool takes explicit owner/repo, so "now check the biggest fork"
  is just the same tools pointed at a different repository — no special path.
"""

from __future__ import annotations

from . import github as gh_tools
from . import osv as osv_tools

REASONING = {
    "type": "string",
    "description": ("Case notes, required: what the last finding was and why this step is next. "
                    "One or two terse sentences — this goes verbatim into the investigation log a human reads. "
                    "When batching several calls in one response, each call's note says what THAT call is for; "
                    "never repeat one note across the batch."),
}

_OWNER = {"type": "string", "description": "Repository owner login. Explicit on purpose — point tools at any repo (e.g. a fork)."}
_REPO = {"type": "string", "description": "Repository name."}


def _schema(props: dict, required: list[str], repo_scoped: bool = True) -> dict:
    properties = {"reasoning": REASONING}
    req = ["reasoning"]
    if repo_scoped:
        properties.update({"owner": _OWNER, "repo": _REPO})
        req += ["owner", "repo"]
    properties.update(props)
    return {"type": "object", "properties": properties, "required": req + required}


def _tool(name: str, description: str, schema: dict) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": schema}}


TOOL_SPECS: list[dict] = [
    _tool("get_repo",
          "Repository overview: stars, forks, dates, license, archived/disabled/fork status. "
          "Useful for sizing up any repo, including forks.",
          _schema({}, [])),
    _tool("list_commits",
          "Recent commits, newest first (max 30/call). Filter with since/until (ISO 8601) and author "
          "(GitHub login) — the workhorse for activity timelines and 'what did X do in that window'.",
          _schema({
              "since": {"type": "string", "description": "ISO date, e.g. 2022-03-01"},
              "until": {"type": "string", "description": "ISO date"},
              "author": {"type": "string", "description": "GitHub login to filter by"},
              "per_page": {"type": "integer", "maximum": 30},
          }, [])),
    _tool("get_commit",
          "Full detail of one commit: message, stats, and capped diffs (largest files first). "
          "Use to inspect a suspicious commit's actual code.",
          _schema({"sha": {"type": "string"}}, ["sha"])),
    _tool("list_contributors",
          "Top contributors with commit counts AND share % of the top-30 total — the bus-factor signal. "
          "One person dominating is a lead worth following.",
          _schema({}, [])),
    _tool("list_issues",
          "Recent issues (PRs excluded), with per-issue comment counts and a computed summary of how many "
          "are unanswered — responsiveness signal.",
          _schema({
              "state": {"type": "string", "enum": ["open", "closed", "all"]},
              "sort": {"type": "string", "enum": ["created", "updated", "comments"]},
              "per_page": {"type": "integer", "maximum": 20},
          }, [])),
    _tool("get_issue",
          "One issue (or PR) in depth: body plus first comments. Use to read the actual discussion "
          "behind a signal (a deprecation notice, an incident thread).",
          _schema({"number": {"type": "integer"}}, ["number"])),
    _tool("list_pulls",
          "Recent pull requests with merged dates — merged-PR recency is the best 'is anyone home' signal.",
          _schema({
              "state": {"type": "string", "enum": ["open", "closed", "all"]},
              "per_page": {"type": "integer", "maximum": 20},
          }, [])),
    _tool("list_releases",
          "Recent GitHub releases (falls back to tags automatically when a project never cut releases).",
          _schema({}, [])),
    _tool("get_file",
          "Read a file from the repo (truncated at 6KB). ref = branch/tag/sha for historical reads. "
          "README for notices, package.json/manifest for the published package name.",
          _schema({
              "path": {"type": "string", "description": "e.g. README.md or package.json"},
              "ref": {"type": "string", "description": "optional branch, tag, or commit sha"},
          }, ["path"])),
    _tool("list_forks",
          "Top forks by stars with last-push dates — did the community move its maintenance elsewhere? "
          "Any fork can then be investigated with the normal tools.",
          _schema({}, [])),
    _tool("get_security_advisories",
          "Repository-published security advisories. Often empty even for CVE'd projects — "
          "cross-check with osv_query.",
          _schema({}, [])),
    _tool("osv_query",
          "Query the OSV vulnerability database by published package name (+ecosystem, e.g. npm/PyPI) "
          "or by commit sha. The reliable path to CVEs; keyless.",
          _schema({
              "package": {"type": "string", "description": "published package name, e.g. from package.json"},
              "ecosystem": {"type": "string", "description": "npm, PyPI, Go, crates.io, Maven... (default npm)"},
              "version": {"type": "string", "description": "optional specific version"},
              "commit": {"type": "string", "description": "alternative: query by commit sha"},
          }, [], repo_scoped=False)),
    _tool("get_user",
          "A user's public profile: account age, repos, followers, bio. Who is this maintainer?",
          _schema({"login": {"type": "string"}}, ["login"], repo_scoped=False)),
    _tool("get_user_events",
          "A user's recent public activity (GitHub only serves ~90 days). Is the maintainer still around "
          "RIGHT NOW? For history, use list_commits(author=...).",
          _schema({"login": {"type": "string"}}, ["login"], repo_scoped=False)),
    # ------------------------- control tools -------------------------- #
    _tool("request_more_budget",
          "Pause and ask the human for more LLM calls. Use when the budget is nearly gone but a decisive "
          "lead remains. Make the case: findings so far, what you still need, and exactly what you'd do.",
          _schema({
              "argument": {"type": "string", "description": "Your pitch: what you found and why more calls will change or solidify the verdict."},
              "planned_steps": {"type": "array", "items": {"type": "string"}, "description": "The specific next steps, one per call."},
              "calls_requested": {"type": "integer", "minimum": 1, "maximum": 30},
          }, ["argument", "planned_steps", "calls_requested"], repo_scoped=False)),
    _tool("render_verdict",
          "Conclude the investigation. Evidence is validated mechanically: each data_point must be a "
          "VERBATIM quote from the cited step's result — paraphrases are rejected and returned to you. "
          "To skip the middle of a long result write 'start ... end': every fragment verbatim, in order.",
          _schema({
              "decision": {"type": "string", "enum": ["adopt", "adopt_with_conditions", "reject"]},
              "summary": {"type": "string", "description": "The story of the case in one short paragraph."},
              "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
              "evidence": {
                  "type": "array", "minItems": 1,
                  "items": {
                      "type": "object",
                      "properties": {
                          "claim": {"type": "string", "description": "The factual claim supporting the verdict."},
                          "step_id": {"type": "integer", "description": "Log step where this was observed."},
                          "data_point": {"type": "string", "description": "Verbatim quote (10+ chars) copied from that step's tool result. "
                                                        "'...' may join verbatim fragments (5+ chars each) in the order they appear."},
                      },
                      "required": ["claim", "step_id", "data_point"],
                  },
              },
              "conditions": {"type": "array", "items": {"type": "string"},
                             "description": "Required when decision is adopt_with_conditions."},
              "unverified_notes": {"type": "array", "items": {"type": "string"},
                                   "description": "What could NOT be verified (errors, rate limits, gaps)."},
              "changed_from_previous": {"type": "string",
                                        "description": "Only when revising an earlier verdict: what changed and why."},
          }, ["decision", "summary", "evidence"], repo_scoped=False)),
]

CONTROL_TOOLS = {"request_more_budget", "render_verdict"}

# Mounted alone during the one-shot wrap-up call after a budget denial: the agent
# can only conclude, not investigate — the hard stop is mechanical, not an instruction.
VERDICT_ONLY_SPECS = [t for t in TOOL_SPECS if t["function"]["name"] == "render_verdict"]

IMPLEMENTATIONS = {
    "get_repo": gh_tools.get_repo,
    "list_commits": gh_tools.list_commits,
    "get_commit": gh_tools.get_commit,
    "list_contributors": gh_tools.list_contributors,
    "list_issues": gh_tools.list_issues,
    "get_issue": gh_tools.get_issue,
    "list_pulls": gh_tools.list_pulls,
    "list_releases": gh_tools.list_releases,
    "get_file": gh_tools.get_file,
    "list_forks": gh_tools.list_forks,
    "get_security_advisories": gh_tools.get_security_advisories,
    "osv_query": osv_tools.osv_query,
    "get_user": gh_tools.get_user,
    "get_user_events": gh_tools.get_user_events,
}


def dispatch(gh, name: str, args: dict) -> tuple[str, int]:
    """Run a tool; never raises — failures become observations the agent can reason about."""
    fn = IMPLEMENTATIONS.get(name)
    if fn is None:
        return f"ERROR (unknown_tool): no tool named '{name}'.", 0
    try:
        return fn(gh, args)
    except KeyError as exc:
        return f"ERROR (missing_argument): {name} requires argument {exc}.", 0
    except Exception as exc:  # defensive: a tool bug must not kill the investigation
        return f"ERROR (tool_failure): {name} crashed: {exc.__class__.__name__}: {exc}", 0
