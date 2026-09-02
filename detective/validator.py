"""Mechanical evidence validation — the anti-folklore gate.

The LLM knows these repos' stories from training data. The rule that keeps
memory out of verdicts: every evidence data_point must be a VERBATIM quote
from the cited log step's stored observation. Verbatim quotes make validation
a whitespace-normalized substring check — simple and unfoolable. A failed
check rejects the render_verdict call with a precise error, and the agent
must re-cite from what it actually observed.

Elisions: a long tool result is naturally quoted as "start ... end". That is
still mechanically checkable — each "..."-separated fragment must be verbatim
and appear in order — so it is accepted rather than costing a budget call
(the second live run lost call 29 of 30 to exactly this rejection).
"""

from __future__ import annotations

import re

MIN_QUOTE_CHARS = 10
MIN_FRAGMENT_CHARS = 5

_CITATION_RE = re.compile(r"\[step\s+(\d+)\]", re.IGNORECASE)
# "...", "…", "[...]" or "(...)" inside a quote marks skipped text.
_ELLIPSIS_RE = re.compile(r"\s*(?:[\[(]\s*(?:\.{3,}|…)\s*[\])]|\.{3,}|…)\s*")


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _fragments(quote: str) -> list[str]:
    return [f for f in _ELLIPSIS_RE.split(_norm(quote)) if f]


def _first_missing(fragments: list[str], haystack: str) -> str | None:
    """The first fragment not found in order (each search starts after the previous match), or None."""
    pos = 0
    for frag in fragments:
        idx = haystack.find(frag, pos)
        if idx < 0:
            return frag
        pos = idx + len(frag)
    return None


def check_evidence(evidence: list[dict] | None, log: list[dict]) -> tuple[list[str], list[dict]]:
    """Returns (errors, annotated_evidence). annotated items carry verified: bool."""
    errors: list[str] = []
    annotated: list[dict] = []
    by_id = {entry["id"]: entry for entry in log}

    if not evidence:
        errors.append("evidence[] is empty — a verdict needs at least one grounded item")
        return errors, annotated

    for i, item in enumerate(evidence):
        item = dict(item)
        step_id = item.get("step_id")
        fragments = _fragments(item.get("data_point"))
        short = [f for f in fragments if len(f) < MIN_FRAGMENT_CHARS]
        problem = None
        if not item.get("claim"):
            problem = f"evidence[{i}] has an empty claim"
        elif step_id not in by_id:
            problem = f"evidence[{i}] cites step {step_id}, which does not exist in the log"
        elif sum(len(f) for f in fragments) < MIN_QUOTE_CHARS:
            problem = (f"evidence[{i}].data_point is too short to verify — "
                       f"quote at least {MIN_QUOTE_CHARS} characters verbatim from the tool result")
        elif short:
            problem = (f"evidence[{i}].data_point has a fragment too short to verify (\"{short[0]}\") — each "
                       f"'...'-separated fragment must be at least {MIN_FRAGMENT_CHARS} characters of verbatim text")
        else:
            missing = _first_missing(fragments, _norm(by_id[step_id]["observation"]))
            if missing is not None and len(fragments) == 1:
                problem = (f"evidence[{i}] cites step {step_id}, but that step's result does not contain "
                           f"the quoted data_point: \"{(item.get('data_point') or '')[:80]}\" — "
                           "copy the quote verbatim from the tool result")
            elif missing is not None:
                problem = (f"evidence[{i}] cites step {step_id}, but the fragment \"{missing[:60]}\" of the quoted "
                           "data_point is not in that step's result (in order) — every '...'-separated fragment "
                           "must be verbatim and in the order it appears in the tool result")
        item["verified"] = problem is None
        annotated.append(item)
        if problem:
            errors.append(problem)
    return errors, annotated


def invalid_citations(text: str, log: list[dict]) -> list[int]:
    """For chat answers: [step N] citations that don't exist in the log."""
    ids = {entry["id"] for entry in log}
    return sorted({int(m) for m in _CITATION_RE.findall(text or "")} - ids)
