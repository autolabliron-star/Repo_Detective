"""Chat over a finished investigation.

Two paths, and they are architecturally different on purpose:
- QUESTION → answered from the STORED LOG only (no GitHub tools are even
  mounted on this path), with [step N] citations validated against the log.
  These calls are uncounted — the budget belongs to the investigation.
- RETASK  → the directive is appended to the persisted message history and
  the SAME agent loop resumes with the remaining budget; a new verdict, if
  rendered, is appended as v2/v3 with what changed.
"""

from __future__ import annotations

import sys

from . import term
from .agent import run_investigation
from .investigation import Investigation, STATUS_PAUSED
from .llm import LLMClient
from .prompts import CLASSIFIER_SYSTEM, QA_SYSTEM_TEMPLATE
from .report import write_report
from .validator import invalid_citations

_OBS_CAP = 600  # chars of each observation included in Q&A context


def _build_material(inv: Investigation) -> str:
    parts = ["--- INTAKE ---"]
    intake = inv.state["intake"]
    parts.append(f"{inv.full_name}: {intake.get('description') or 'no description'}; "
                 f"{intake.get('stars')} stars; last push {intake.get('pushed_at')}; "
                 f"archived: {intake.get('archived')}; warnings: {'; '.join(intake.get('warnings') or ['none'])}")
    parts.append("\n--- INVESTIGATION LOG ---")
    for e in inv.log:
        obs = (e["observation"] or "").strip()
        if len(obs) > _OBS_CAP:
            obs = obs[:_OBS_CAP] + " …[truncated]"
        parts.append(f"[step {e['id']}] {e['tool']}({e['args']}) — notes: {e['reasoning']}\n  result: {obs}")
    parts.append("\n--- VERDICTS ---")
    for v in inv.state["verdicts"]:
        ev = "; ".join(f"(step {i.get('step_id')}) {i.get('claim')}" for i in v.get("evidence", []))
        parts.append(f"v{v['version']} [{v['trigger']}]: {v['decision']} — {v['summary']} | evidence: {ev} "
                     f"| conditions: {'; '.join(v.get('conditions') or ['none'])}"
                     f"| unverified: {'; '.join(v.get('unverified_notes') or ['none'])}")
    if not inv.state["verdicts"]:
        parts.append("(no verdict was rendered)")
    return "\n".join(parts)


def _classify(llm: LLMClient, text: str) -> str:
    msg = llm.complete(
        [{"role": "system", "content": CLASSIFIER_SYSTEM}, {"role": "user", "content": text}],
        max_tokens=8,
    )
    return "retask" if "retask" in (msg.content or "").strip().lower() else "question"


def _answer_question(inv: Investigation, llm: LLMClient, question: str) -> str:
    system = QA_SYSTEM_TEMPLATE.format(full_name=inv.full_name, material=_build_material(inv))
    messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]
    msg = llm.complete(messages, max_tokens=800)
    answer = msg.content or "(no answer)"
    bad = invalid_citations(answer, inv.log)
    if bad:
        messages += [{"role": "assistant", "content": answer},
                     {"role": "user", "content": f"Your answer cites step(s) {bad}, which do not exist in the log. "
                                                 "Correct the citations using only real steps."}]
        answer = llm.complete(messages, max_tokens=800).content or answer
        bad = invalid_citations(answer, inv.log)
        if bad:
            answer += term.red(f"\n(warning: citations to non-existent steps {bad} — treat those lines with suspicion)")
    return answer


def _retask(inv: Investigation, llm: LLMClient, gh, directive: str) -> None:
    remaining = inv.budget_remaining()
    print(term.dim(f"Resuming the investigation ({remaining} LLM calls remaining)…"))
    inv.messages.append({"role": "user", "content":
                         f"[re-task from the tech lead] {directive}\n"
                         "Continue the investigation. If the new evidence warrants it, update the verdict with "
                         "render_verdict (fill changed_from_previous); otherwise render it again unchanged, "
                         "stating why the evidence didn't move it."})
    inv.save()
    before = len(inv.state["verdicts"])
    run_investigation(inv, llm, gh, phase=f"retask: {directive[:80]}")
    after = inv.latest_verdict()
    if after and len(inv.state["verdicts"]) > before and before > 0:
        prev = inv.state["verdicts"][before - 1]
        if prev["decision"] != after["decision"]:
            print(term.bold(term.yellow(f"Verdict changed: {prev['decision']} → {after['decision']} (v{after['version']})")))
        else:
            print(term.dim(f"Verdict unchanged ({after['decision']}, now v{after['version']})."))


def run_chat(inv: Investigation, llm: LLMClient, gh) -> None:
    v = inv.latest_verdict()
    print(term.rule("═"))
    print(term.bold(f"💬 Case file: {inv.full_name}"))
    if v:
        print(f"Verdict: {term.bold(v['decision'])} (v{v['version']}) · "
              f"budget: {inv.budget_used()}/{inv.budget_granted()} used, {inv.budget_remaining()} left")
    else:
        print(f"No verdict yet (status: {inv.status}) · budget: {inv.budget_used()}/{inv.budget_granted()} used")
    print(term.dim("Ask about the investigation, or give a directive (e.g. “now check the biggest fork”).\n"
                   "Commands: /report  /log  /budget  /quit"))
    print(term.rule("═"))

    if inv.status == STATUS_PAUSED:
        print(term.yellow("This investigation is paused awaiting a budget decision — resuming it now."))
        _retask(inv, llm, gh, "continue where you left off")

    while True:
        try:
            text = input(term.bold("you> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not text:
            continue
        if text in ("/quit", "/exit", "exit", "quit"):
            return
        if text == "/report":
            print((inv.dir / "report.md").read_text() if (inv.dir / "report.md").exists()
                  else term.yellow("no report yet"))
            continue
        if text == "/log":
            for e in inv.log:
                err = term.red(" ⚠") if e.get("error") else ""
                print(f"  step {e['id']:>2} [{e['tool']}]{err} {e['reasoning'][:100]}")
            continue
        if text == "/budget":
            print(f"  {inv.budget_used()}/{inv.budget_granted()} calls used, {inv.budget_remaining()} remaining")
            for e in inv.state["budget"]["extensions"]:
                print(f"  extension: +{e['granted']} ({e['decided_by']})")
            continue

        if _classify(llm, text) == "retask":
            if inv.budget_remaining() == 0:
                print(term.yellow("The budget is fully spent — the agent will have to ask for an extension."))
            _retask(inv, llm, gh, text)
        else:
            print(f"\n{_answer_question(inv, llm, text)}\n")
