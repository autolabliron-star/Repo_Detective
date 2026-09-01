"""Mechanical evidence validation — the anti-folklore gate.

The LLM knows these repos' stories from training data. The rule that keeps
memory out of verdicts: every evidence data_point must be a VERBATIM quote
from the cited log step's stored observation. Verbatim quotes make validation
a whitespace-normalized substring check — simple and unfoolable. A failed
check rejects the render_verdict call with a precise error, and the agent
must re-cite from what it actually observed.
"""

from __future__ import annotations

import re

MIN_QUOTE_CHARS = 10

_CITATION_RE = re.compile(r"\[step\s+(\d+)\]", re.IGNORECASE)


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


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
        quote = _norm(item.get("data_point"))
        problem = None
        if not item.get("claim"):
            problem = f"evidence[{i}] has an empty claim"
        elif step_id not in by_id:
            problem = f"evidence[{i}] cites step {step_id}, which does not exist in the log"
        elif len(quote) < MIN_QUOTE_CHARS:
            problem = (f"evidence[{i}].data_point is too short to verify — "
                       f"quote at least {MIN_QUOTE_CHARS} characters verbatim from the tool result")
        elif quote not in _norm(by_id[step_id]["observation"]):
            problem = (f"evidence[{i}] cites step {step_id}, but that step's result does not contain "
                       f"the quoted data_point: \"{(item.get('data_point') or '')[:80]}\" — "
                       "copy the quote verbatim from the tool result")
        item["verified"] = problem is None
        annotated.append(item)
        if problem:
            errors.append(problem)
    return errors, annotated


def invalid_citations(text: str, log: list[dict]) -> list[int]:
    """For chat answers: [step N] citations that don't exist in the log."""
    ids = {entry["id"] for entry in log}
    return sorted({int(m) for m in _CITATION_RE.findall(text or "")} - ids)
