"""Report renderer — plain code, no LLM.

Renders state.json into a readable case file with a story arc:
The Tip-off (intake) -> The Investigation (every step, dead ends included) ->
The Verdict (validated evidence only; anything unverified is labeled).
Steps that leave the target repo (a fork, a maintainer's profile, OSV) are
marked as followed leads — those are the twists.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .investigation import Investigation

_DECISION_LABEL = {
    "adopt": "✅ ADOPT",
    "adopt_with_conditions": "⚠️ ADOPT WITH CONDITIONS",
    "reject": "🛑 REJECT",
}

_LEAD_TOOLS = {"get_user", "get_user_events", "osv_query", "list_forks"}


def _n(x) -> str:
    return f"{x:,}" if isinstance(x, int) else "?"


def _is_lead(inv: Investigation, entry: dict) -> bool:
    if entry["tool"] in _LEAD_TOOLS:
        return True
    owner = entry["args"].get("owner")
    return bool(owner) and f"{owner}/{entry['args'].get('repo', '')}".lower() != inv.full_name.lower()


def render_markdown(inv: Investigation) -> str:
    intake = inv.state["intake"]
    verdict = inv.latest_verdict()
    lines: list[str] = [f"# The Case of {inv.full_name}", ""]

    # ------------------------------ verdict ---------------------------- #
    if verdict:
        label = _DECISION_LABEL.get(verdict["decision"], verdict["decision"])
        rev = f" · v{verdict['version']}, revised after re-task: “{verdict['trigger'].removeprefix('retask: ')}”" \
            if verdict["version"] > 1 else ""
        conf = f" · confidence: {verdict['confidence']}" if verdict.get("confidence") else ""
        lines += [f"## Verdict: {label}{conf}{rev}", "", f"> {verdict['summary']}", ""]
        if verdict.get("changed_from_previous"):
            lines += [f"**What changed since the previous verdict:** {verdict['changed_from_previous']}", ""]
        if verdict.get("conditions"):
            lines += ["**Conditions:**", *[f"- {c}" for c in verdict["conditions"]], ""]

        lines.append("**Evidence** (every item mechanically checked against the log):")
        for item in verdict.get("evidence", []):
            mark = "✔" if item.get("verified") else "✘ UNVERIFIED —"
            lines.append(f"- {mark} {item.get('claim')}  \n"
                         f"  _step {item.get('step_id')}:_ “{item.get('data_point')}”")
        lines.append("")
        if verdict.get("unverified_notes"):
            lines += ["**Could not be verified:**", *[f"- {n}" for n in verdict["unverified_notes"]], ""]
        if not verdict.get("validation_passed", True):
            lines += ["> ⚠️ This verdict was rendered with the budget exhausted; the items marked "
                      "UNVERIFIED failed citation validation and must not be trusted as evidence.", ""]
    else:
        lines += ["## Verdict: none rendered",
                  f"_Status: {inv.status}. The investigation gathered the material below but did not reach "
                  "a verdict — resume it from the chat._", ""]

    if len(inv.state["verdicts"]) > 1:
        lines += ["### Verdict history"]
        for v in inv.state["verdicts"]:
            lines.append(f"- v{v['version']} — {_DECISION_LABEL.get(v['decision'], v['decision'])} "
                         f"({v['trigger']}, at {v['budget_used_at_render']} calls used)")
        lines.append("")

    # ------------------------------ intake ----------------------------- #
    lines += ["## The Tip-off (intake — plain code, no LLM)", ""]
    if intake.get("renamed_from"):
        lines.append(f"- **Renamed:** requested `{intake['renamed_from']}`, GitHub redirected to `{inv.full_name}`")
    desc = intake.get("description") or "no description"
    lines += [
        f"- {desc}",
        f"- ⭐ {_n(intake.get('stars'))} stars · {_n(intake.get('forks'))} forks · "
        f"{_n(intake.get('open_issues_and_prs'))} open issues+PRs",
        f"- Language: {intake.get('language')} · License: {intake.get('license') or 'none'}",
        f"- Created {str(intake.get('created_at'))[:10]} · last push {str(intake.get('pushed_at'))[:10]}",
        f"- Releases: {intake.get('release_note')}",
    ]
    if intake.get("top_contributors"):
        top = ", ".join(f"{c['login']} ({c['share_pct']}%)" for c in intake["top_contributors"][:5])
        lines.append(f"- Top contributors: {top}")
    for w in intake.get("warnings", []):
        lines.append(f"- ⚠️ **{w}**")
    lines.append("")

    # --------------------------- investigation ------------------------- #
    lines += ["## The Investigation", ""]
    current_phase = None
    for entry in inv.log:
        if entry["phase"] != current_phase:
            current_phase = entry["phase"]
            if current_phase != "initial":
                lines += [f"### ↩︎ Re-tasked: “{current_phase.removeprefix('retask: ')}”", ""]
        args_str = json.dumps({k: v for k, v in entry["args"].items()}, ensure_ascii=False)
        lead = "  ← *following a lead beyond the repo*" if _is_lead(inv, entry) else ""
        lines.append(f"**Step {entry['id']}** · `{entry['tool']}{args_str}`{lead}")
        if entry.get("reasoning"):
            lines.append(f"> 🗒 _{entry['reasoning']}_")
        obs = entry.get("observation") or ""
        head = "\n".join(obs.splitlines()[:6])
        more = len(obs.splitlines()) - 6
        block = head + (f"\n… ({more} more lines in the stored log)" if more > 0 else "")
        prefix = "⚠️ " if entry.get("error") else ""
        lines += ["", f"```text", f"{prefix}{block}", "```", ""]

    # ------------------------------ budget ----------------------------- #
    b = inv.state["budget"]
    lines += ["## Budget ledger", "",
              f"- Initial budget: {b['initial']} LLM calls · used: {b['used']} · "
              f"remaining: {inv.budget_remaining()}"]
    for e in b["extensions"]:
        lines.append(f"- Extension: requested {e['requested']}, granted {e['granted']} "
                     f"({e['decided_by']}) — “{e['argument'][:120]}”")
    lines += ["",
              f"---",
              f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · every evidence item "
              f"cites an investigation step; anything that couldn't be verified is labeled as such._",
              ""]
    return "\n".join(lines)


def write_report(inv: Investigation) -> str:
    path = inv.dir / "report.md"
    path.write_text(render_markdown(inv))
    return str(path)
