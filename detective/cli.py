"""Command-line entrypoints:

  investigate <url> [--budget N] [--fresh]   run an investigation
  chat <owner/repo | url>                    chat over a finished one / re-task it
  list                                       show stored investigations
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import term
from .agent import run_investigation
from .chat import run_chat
from .github_client import GitHubClient
from .intake import run_intake
from .investigation import Investigation, STATUS_CONCLUDED, STATUS_NO_VERDICT
from .llm import LLMClient

INVESTIGATIONS_ROOT = Path(os.environ.get("INVESTIGATIONS_DIR", "investigations"))

BANNER = """
🔍 The Repo Detective — should we build on this repository?

  investigate a repo:   detective investigate https://github.com/expressjs/express
  chat / re-task:       detective chat expressjs/express
  stored cases:         detective list

Environment: OPENAI_API_KEY, OPENAI_MODEL required; OPENAI_BASE_URL for any
OpenAI-compatible provider; GITHUB_TOKEN optional (raises the API rate limit).
(under docker: docker compose run --rm detective <command>)
"""


def _print_tipoff(intake: dict, gh: GitHubClient) -> None:
    print(f"\n{term.rule('═')}")
    print(term.bold(f"🔍 New case: {intake['canonical_full_name']}"))
    print(term.dim(intake.get("description") or "no description"))
    rel = intake.get("release_note")
    stars = intake.get("stars")
    stars_str = f"{stars:,}" if isinstance(stars, int) else "?"
    print(f"⭐ {stars_str} stars · last push {str(intake.get('pushed_at'))[:10]} · {rel}")
    if intake.get("top_contributors"):
        top = ", ".join(f"{c['login']} ({c['share_pct']}%)" for c in intake["top_contributors"][:3])
        print(f"Top contributors: {top}")
    for w in intake.get("warnings", []):
        print(term.yellow(f"⚠ {w}"))
    print(term.dim(gh.quota_line()))
    print(term.rule("═"))


def cmd_investigate(args: argparse.Namespace) -> int:
    llm = LLMClient()  # fail fast on missing env before touching GitHub
    gh = GitHubClient(cache_dir=INVESTIGATIONS_ROOT / ".httpcache")

    intake, fatal = run_intake(gh, args.url)
    if fatal:
        print(term.red(f"Cannot investigate: {fatal}"))
        return 2
    _print_tipoff(intake, gh)

    existing = Investigation.find(INVESTIGATIONS_ROOT, intake["canonical_full_name"])
    if existing and not args.fresh:
        if existing.status in (STATUS_CONCLUDED, STATUS_NO_VERDICT):
            v = existing.latest_verdict()
            print(term.yellow(f"Already investigated (verdict: {v['decision'] if v else 'none'}). "
                              f"Open the chat with `chat {existing.full_name}`, or rerun with --fresh."))
            return 0
        print(term.dim("Resuming the in-progress investigation…"))
        inv = existing
    else:
        inv = Investigation.create(INVESTIGATIONS_ROOT, intake, budget_initial=args.budget)

    run_investigation(inv, llm, gh)
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    llm = LLMClient()
    gh = GitHubClient(cache_dir=INVESTIGATIONS_ROOT / ".httpcache")
    inv = Investigation.find(INVESTIGATIONS_ROOT, args.target)
    if not inv:
        print(term.red(f"No stored investigation matches {args.target!r}."))
        stored = Investigation.list_all(INVESTIGATIONS_ROOT)
        if stored:
            print("Stored cases:")
            for i in stored:
                print(f"  - {i.full_name}")
        else:
            print("Run an investigation first: detective investigate <repo url>")
        return 2
    run_chat(inv, llm, gh)
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    stored = Investigation.list_all(INVESTIGATIONS_ROOT)
    if not stored:
        print("No investigations stored yet.")
        return 0
    for inv in stored:
        v = inv.latest_verdict()
        verdict = v["decision"] if v else "—"
        print(f"{inv.full_name:<40} {inv.status:<28} verdict: {verdict:<24} "
              f"budget {inv.budget_used()}/{inv.budget_granted()}")
    return 0


def _default_budget() -> int:
    try:
        return int(os.environ.get("DETECTIVE_BUDGET", "") or 30)
    except ValueError:
        return 30


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(BANNER)
        return 0

    parser = argparse.ArgumentParser(prog="detective", description="The Repo Detective")
    sub = parser.add_subparsers(dest="command", required=True)

    p_inv = sub.add_parser("investigate", help="investigate a public GitHub repository")
    p_inv.add_argument("url", help="repository URL or owner/repo")
    p_inv.add_argument("--budget", type=int, default=_default_budget(),
                       help="LLM call budget (default 30, or DETECTIVE_BUDGET)")
    p_inv.add_argument("--fresh", action="store_true", help="discard a stored investigation and start over")
    p_inv.set_defaults(fn=cmd_investigate)

    p_chat = sub.add_parser("chat", help="chat over a finished investigation / re-task the agent")
    p_chat.add_argument("target", help="owner/repo, URL, or slug of a stored investigation")
    p_chat.set_defaults(fn=cmd_chat)

    p_list = sub.add_parser("list", help="list stored investigations")
    p_list.set_defaults(fn=cmd_list)

    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except KeyboardInterrupt:
        print(term.yellow("\nInterrupted — state is saved; rerun the same command to resume."))
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
