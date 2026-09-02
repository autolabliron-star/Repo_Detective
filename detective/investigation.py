"""Investigation state: the log, the budget ledger, verdict history, and the
exact message history (for high-fidelity resume). Persisted atomically to
investigations/<slug>/state.json after every step — a crash never loses count.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1

STATUS_IN_PROGRESS = "in_progress"
STATUS_PAUSED = "paused_awaiting_budget"
STATUS_CONCLUDED = "concluded"
STATUS_NO_VERDICT = "concluded_without_verdict"


def slugify(full_name: str) -> str:
    return full_name.lower().replace("/", "__")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Investigation:
    def __init__(self, directory: Path, state: dict):
        self.dir = Path(directory)
        self.state = state

    # ------------------------- construction --------------------------- #

    @classmethod
    def create(cls, root: Path, intake: dict, budget_initial: int) -> "Investigation":
        slug = slugify(intake["canonical_full_name"])
        directory = Path(root) / slug
        directory.mkdir(parents=True, exist_ok=True)
        state = {
            "schema_version": SCHEMA_VERSION,
            "repo": {
                "input_url": intake.get("input_url"),
                "canonical_full_name": intake["canonical_full_name"],
                "renamed_from": intake.get("renamed_from"),
                "investigated_at": _now(),
            },
            "intake": intake,
            "budget": {"initial": budget_initial, "used": 0, "extensions": []},
            "log": [],
            "verdicts": [],
            "messages": [],
            "status": STATUS_IN_PROGRESS,
            "pending_pitch": None,
        }
        inv = cls(directory, state)
        inv.save()
        return inv

    @classmethod
    def load(cls, root: Path, slug: str) -> "Investigation | None":
        path = Path(root) / slug / "state.json"
        if not path.exists():
            return None
        return cls(path.parent, json.loads(path.read_text()))

    @classmethod
    def find(cls, root: Path, query: str) -> "Investigation | None":
        """Resolve a user-supplied target: URL, owner/repo, or slug."""
        q = query.strip().rstrip("/")
        if "github.com" in q:
            q = "/".join(q.split("github.com/")[-1].split("/")[:2])
        candidates = [slugify(q.removesuffix(".git")), q.lower()]
        for cand in candidates:
            inv = cls.load(root, cand)
            if inv:
                return inv
        return None

    @classmethod
    def list_all(cls, root: Path) -> list["Investigation"]:
        root = Path(root)
        if not root.exists():
            return []
        out = []
        for state_file in sorted(root.glob("*/state.json")):
            try:
                out.append(cls(state_file.parent, json.loads(state_file.read_text())))
            except (OSError, json.JSONDecodeError):
                continue
        return out

    # --------------------------- persistence -------------------------- #

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / "state.json.tmp"
        tmp.write_text(json.dumps(self.state, indent=1, ensure_ascii=False))
        os.replace(tmp, self.dir / "state.json")

    # ----------------------------- budget ----------------------------- #

    def budget_granted(self) -> int:
        b = self.state["budget"]
        return b["initial"] + sum(e["granted"] for e in b["extensions"])

    def budget_used(self) -> int:
        return self.state["budget"]["used"]

    def budget_remaining(self) -> int:
        return max(0, self.budget_granted() - self.budget_used())

    # duck-typed interface consumed by llm.LLMClient
    def remaining(self) -> int:
        return self.budget_remaining()

    def count(self) -> None:
        self.state["budget"]["used"] += 1
        self.save()

    def add_extension(self, requested: int, granted: int, argument: str, decided_by: str) -> None:
        self.state["budget"]["extensions"].append({
            "requested": requested,
            "granted": granted,
            "argument": argument,
            "decided_by": decided_by,
            "at": _now(),
        })
        self.save()

    # ------------------------------ log -------------------------------- #

    def add_log(self, *, phase: str, tool: str, args: dict, reasoning: str,
                observation: str, api_requests: int, error: str | None) -> dict:
        entry = {
            "id": len(self.state["log"]) + 1,
            "ts": _now(),
            "call": self.budget_used(),  # which LLM call produced this step (several steps can share one call)
            "phase": phase,
            "tool": tool,
            "args": args,
            "reasoning": reasoning,
            "observation": observation,
            "api_requests": api_requests,
            "error": error,
            "budget_after": self.budget_remaining(),
        }
        self.state["log"].append(entry)
        self.save()
        return entry

    @property
    def log(self) -> list[dict]:
        return self.state["log"]

    @property
    def messages(self) -> list[dict]:
        return self.state["messages"]

    # ---------------------------- verdicts ----------------------------- #

    def add_verdict(self, verdict: dict, trigger: str) -> dict:
        verdict = dict(verdict)
        verdict["version"] = len(self.state["verdicts"]) + 1
        verdict["trigger"] = trigger
        verdict["budget_used_at_render"] = self.budget_used()
        verdict["rendered_at"] = _now()
        self.state["verdicts"].append(verdict)
        self.save()
        return verdict

    def latest_verdict(self) -> dict | None:
        return self.state["verdicts"][-1] if self.state["verdicts"] else None

    # ----------------------------- status ------------------------------ #

    @property
    def status(self) -> str:
        return self.state["status"]

    def set_status(self, status: str) -> None:
        self.state["status"] = status
        self.save()

    @property
    def full_name(self) -> str:
        return self.state["repo"]["canonical_full_name"]

    @property
    def slug(self) -> str:
        return slugify(self.full_name)
