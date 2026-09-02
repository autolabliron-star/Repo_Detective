"""The agent loop — the heart of the assignment.

A hand-rolled tool-calling loop: LLM response -> dispatch tools -> feed results
back -> repeat, until render_verdict passes validation or the budget forces a
pause. Design points:

- Budget: one successful LLM response = 1 call (however many parallel tool
  calls it carries), enforced at the single choke point in llm.py.
- Reserved pitch: at 2 calls remaining the agent is nudged to conclude or make
  its case — the pause pitch itself costs a call, so waiting for 0 is too late.
- Pause is persisted state: approval/denial survives a process restart, and a
  denial grants exactly 1 wrap-up call so a verdict can still be rendered.
- Every step (including control calls, errors, and failed validations) is a
  first-class investigation-log entry, streamed live to the terminal.
"""

from __future__ import annotations

import json
import re
import sys

from . import term
from .investigation import (
    Investigation,
    STATUS_CONCLUDED,
    STATUS_IN_PROGRESS,
    STATUS_NO_VERDICT,
    STATUS_PAUSED,
)
from .llm import BudgetExhausted, LLMClient
from .prompts import build_initial_user, build_system_prompt
from .report import write_report
from .tools.registry import IMPLEMENTATIONS, TOOL_SPECS, VERDICT_ONLY_SPECS, dispatch
from .validator import check_evidence


# ------------------------------ helpers -------------------------------- #

def _serialize_assistant(msg) -> dict:
    """Whitelist the fields we persist/replay — provider-specific extras are dropped."""
    out: dict = {"role": "assistant", "content": msg.content}
    if msg.tool_calls:
        out["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]
    return out


def _tool_result(inv: Investigation, call_id: str, name: str, content: str) -> None:
    inv.messages.append({"role": "tool", "tool_call_id": call_id, "name": name, "content": content})


def _public_args(args: dict) -> dict:
    return {k: v for k, v in args.items() if k != "reasoning"}


def _extract_error(observation: str) -> str | None:
    if observation.startswith("ERROR ("):
        return observation.split(")", 1)[0].removeprefix("ERROR (")
    return None


_REASONING_RE = re.compile(r'"reasoning"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _salvage_reasoning(raw: str) -> str:
    """Pull the case notes out of arguments that failed to parse (truncated JSON) so the log keeps the 'why'."""
    m = _REASONING_RE.search(raw or "")
    if not m:
        return ""
    try:
        return json.loads(f'"{m.group(1)}"')
    except json.JSONDecodeError:
        return m.group(1)


COMPACT_HINT = ("Re-issue it COMPACTLY: for render_verdict keep the summary to 3 sentences, at most 6 evidence "
                "items, and each data_point a SHORT verbatim fragment (10-120 chars) — not whole lines.")


def repair_messages(inv: Investigation) -> None:
    """If a previous run died between the assistant message and its tool results,
    the history ends with unanswered tool_calls — the API would reject it."""
    msgs = inv.messages
    if msgs and msgs[-1].get("role") == "assistant" and msgs[-1].get("tool_calls"):
        for tc in msgs[-1]["tool_calls"]:
            _tool_result(inv, tc["id"], tc["function"]["name"],
                         "ERROR (interrupted): the previous session ended before this ran — re-issue if still needed.")
        inv.save()


def _stream_call_header(inv: Investigation, msg, finish: str | None, wrapup: bool) -> None:
    """One line per LLM call so a reader can see that steps are batched — 38 steps is not 38 calls."""
    n = len(msg.tool_calls or [])
    label = f"LLM call {inv.budget_used()}/{inv.budget_granted()} · {n} tool call{'s' if n != 1 else ''}"
    if wrapup:
        label += " · wrap-up (render_verdict only)"
    if finish == "length":
        label += term.red(" · OUTPUT TRUNCATED")
    print(f"\n{term.dim('── ' + label)}")


def _stream_step(entry: dict) -> None:
    args_str = json.dumps(_public_args(entry["args"]), ensure_ascii=False)
    print(f"\n{term.bold('Step ' + str(entry['id']))} · {term.cyan(entry['tool'])} {term.dim(args_str)}")
    if entry["reasoning"]:
        print(f"  {term.magenta('🗒')} {entry['reasoning']}")
    first_line = (entry["observation"] or "").splitlines()[0][:140] if entry["observation"] else ""
    marker = term.red("⚠ ") if entry["error"] else ""
    print(f"  {marker}{term.dim('→')} {first_line}")


# ------------------------- human-in-the-loop ---------------------------- #

def _ask_human_for_budget(requested: int) -> int:
    """Returns calls granted (0 = denied). Auto-denies when non-interactive — never hangs."""
    if not sys.stdin.isatty():
        print(term.yellow("(non-interactive session — extension auto-denied)"))
        return 0
    try:
        answer = input(term.bold(f"Grant {requested} more LLM calls? [y = grant {requested} / a number = custom / n = deny] > ")).strip().lower()
    except EOFError:
        print(term.yellow("(no input available — extension auto-denied)"))
        return 0
    if answer in ("y", "yes"):
        return requested
    if answer.isdigit():
        return int(answer)
    return 0


def _handle_pause(inv: Investigation, pitch: dict | None, phase: str) -> bool:
    """Budget is gone (or the agent proactively asked). Show the case, ask the human.
    Returns True if extra calls were granted; on denial grants exactly 1 wrap-up call."""
    inv.set_status(STATUS_PAUSED)
    print(f"\n{term.rule('═')}")
    print(term.bold(term.yellow("⏸  BUDGET PAUSE — the agent needs a human decision")))
    print(f"Used {inv.budget_used()}/{inv.budget_granted()} LLM calls on {inv.full_name}.")

    if pitch:
        requested = int(pitch.get("calls_requested", 10))
        inv.state["pending_pitch"] = pitch
        inv.save()
        print(f"\n{term.bold('The agent’s case for more budget:')}\n{pitch.get('argument', '(no argument given)')}")
        steps = pitch.get("planned_steps") or []
        if steps:
            print(term.bold("Planned steps:"))
            for i, s in enumerate(steps, 1):
                print(f"  {i}. {s}")
    else:
        requested = 10
        print(term.bold("\nThe budget ran out before the agent could conclude. Latest case notes:"))
        for entry in inv.log[-3:]:
            print(f"  step {entry['id']} [{entry['tool']}]: {entry['reasoning'] or '(no notes)'}")
        print(f"Granting more calls lets it finish; denying forces a best-effort verdict now.")

    granted = _ask_human_for_budget(requested)
    if granted > 0:
        inv.add_extension(requested, granted, (pitch or {}).get("argument", "budget exhausted mid-investigation"),
                          decided_by="human")
        inv.state["wrapup_granted"] = False  # a real grant resets the one-shot wrap-up
        print(term.green(f"✔ Granted +{granted} calls (budget now {inv.budget_granted()})."))
    else:
        # 1 wrap-up call, earmarked for render_verdict — a denial must not strand the case without a
        # verdict. Granted AT MOST ONCE, and the wrap-up call only mounts the render_verdict tool, so
        # the budget cannot creep past the denial (a bare instruction doesn't bind the model).
        inv.add_extension(requested, 1, "denied — 1 wrap-up call granted for render_verdict only",
                          decided_by="human (denied)" if sys.stdin.isatty() else "auto (non-interactive)")
        inv.state["wrapup_granted"] = True
        print(term.yellow("✘ Denied — the agent gets exactly 1 wrap-up call to render its best-effort verdict."))
    inv.state["pending_pitch"] = None
    inv.set_status(STATUS_IN_PROGRESS)
    print(term.rule("═"))
    return granted > 0


# ----------------------------- control tools ---------------------------- #

def _handle_budget_request(inv: Investigation, call_id: str, args: dict, phase: str) -> None:
    granted = _handle_pause(inv, args, phase)
    ext = inv.state["budget"]["extensions"][-1]
    inv.add_log(phase=phase, tool="request_more_budget", args=_public_args(args),
                reasoning=args.get("reasoning", ""),
                observation=f"requested {args.get('calls_requested')} more calls; human granted {ext['granted']}",
                api_requests=0, error=None)
    if granted:
        _tool_result(inv, call_id, "request_more_budget",
                     f"Granted +{ext['granted']} calls (budget now {inv.budget_granted()}). Continue the investigation.")
    else:
        _tool_result(inv, call_id, "request_more_budget",
                     "Denied. You have exactly 1 call left: render_verdict now with your best-supported "
                     "decision, and list everything unverified in unverified_notes.")


def _handle_verdict(inv: Investigation, call_id: str, args: dict, phase: str) -> bool:
    """Returns True when the verdict is accepted."""
    errors, annotated = check_evidence(args.get("evidence"), inv.log)
    if args.get("decision") == "adopt_with_conditions" and not args.get("conditions"):
        errors.append("decision is adopt_with_conditions but conditions[] is empty — state the conditions")

    if errors and inv.budget_remaining() > 0:
        inv.add_log(phase=phase, tool="render_verdict", args={"decision": args.get("decision")},
                    reasoning=args.get("reasoning", ""),
                    observation="VALIDATION FAILED: " + " | ".join(errors),
                    api_requests=0, error="validation_failed")
        _tool_result(inv, call_id, "render_verdict",
                     "VALIDATION FAILED — verdict not recorded:\n- " + "\n- ".join(errors)
                     + "\nEvery data_point must be a verbatim quote from the cited step's result. Fix and render again.")
        return False

    # Accepted — or forced through with 0 budget left: failing items are visibly UNVERIFIED, never silently kept.
    verdict = {
        "decision": args.get("decision"),
        "summary": args.get("summary", ""),
        "confidence": args.get("confidence"),
        "evidence": annotated,
        "conditions": args.get("conditions") or [],
        "unverified_notes": args.get("unverified_notes") or [],
        "changed_from_previous": args.get("changed_from_previous"),
        "validation_passed": not errors,
        "validation_errors": errors,
    }
    inv.state["wrapup_granted"] = False  # the wrap-up (if any) served its purpose
    recorded = inv.add_verdict(verdict, trigger=phase)
    inv.add_log(phase=phase, tool="render_verdict", args={"decision": verdict["decision"]},
                reasoning=args.get("reasoning", ""),
                observation=f"verdict v{recorded['version']} recorded: {verdict['decision']}"
                            + ("" if not errors else f" ({len(errors)} evidence items failed validation, marked UNVERIFIED)"),
                api_requests=0, error=None)
    _tool_result(inv, call_id, "render_verdict", f"Verdict recorded (v{recorded['version']}).")
    return True


# ------------------------------ the loop -------------------------------- #

def run_investigation(inv: Investigation, llm: LLMClient, gh, phase: str = "initial") -> None:
    if not inv.messages:
        inv.messages.append({"role": "system", "content": build_system_prompt(inv.full_name)})
        inv.messages.append({"role": "user", "content": build_initial_user(inv.state["intake"])})
        inv.save()

    repair_messages(inv)

    # A pause left pending from a previous session (e.g. the process was killed at the prompt).
    if inv.status == STATUS_PAUSED:
        _handle_pause(inv, inv.state.get("pending_pitch"), phase)

    inv.set_status(STATUS_IN_PROGRESS)
    no_tool_strikes = 0
    single_call_streak = 0

    while True:
        # Mid-case checkpoint: at half budget, make the agent name its working verdict and the one open
        # question — the second half goes to what could change the verdict, not to completing a checklist.
        half = inv.state["budget"]["initial"] // 2
        if (half > 2 and inv.budget_remaining() == half and not inv.state.get("wrapup_granted")
                and inv.state.get("checkpoint_at") != inv.budget_granted()):
            inv.state["checkpoint_at"] = inv.budget_granted()
            inv.messages.append({"role": "user", "content":
                                 "[budget controller] Half the budget is spent. In your next case note state your "
                                 "working verdict and the single open question that could still change it, then pursue "
                                 "only that — batching independent lookups into one response. If nothing could change "
                                 "it, render_verdict now."})
            inv.save()

        # Reserved pitch: with 2 calls left, force the choice (once per grant level).
        if inv.budget_remaining() == 2 and inv.state.get("nudged_at") != inv.budget_granted():
            inv.state["nudged_at"] = inv.budget_granted()
            inv.messages.append({"role": "user", "content":
                                 "[budget controller] 2 calls remain. Do not start new leads: either "
                                 "render_verdict now, or request_more_budget with your pitch."})
            inv.save()

        # Wrap-up mode: after a denial, the single remaining call mounts ONLY render_verdict (forced) —
        # the agent physically cannot spend it investigating.
        wrapup = bool(inv.state.get("wrapup_granted")) and inv.budget_remaining() <= 1
        tools = VERDICT_ONLY_SPECS if wrapup else TOOL_SPECS
        tool_choice = {"type": "function", "function": {"name": "render_verdict"}} if wrapup else None

        try:
            msg = llm.complete(inv.messages, tools=tools, budget=inv, tool_choice=tool_choice)
        except BudgetExhausted:
            if inv.state.get("wrapup_granted"):
                # The one-shot wrap-up was already spent without a verdict — hard stop, never creep.
                inv.set_status(STATUS_NO_VERDICT)
                write_report(inv)
                print(term.red("Budget spent and the wrap-up call produced no verdict — hard stop. "
                               f"The material gathered is in the report: {inv.dir / 'report.md'}"))
                return
            if _handle_pause(inv, None, phase):
                continue
            inv.messages.append({"role": "user", "content":
                                 "[budget controller] Extension denied. You have exactly 1 call: "
                                 "render_verdict now, marking unverified gaps. Keep it compact — at most 6 "
                                 "evidence items with short verbatim quotes."})
            inv.save()
            continue

        finish = getattr(llm, "last_finish_reason", None)
        inv.messages.append(_serialize_assistant(msg))
        inv.save()
        _stream_call_header(inv, msg, finish, wrapup)

        if wrapup and not any(tc.function.name == "render_verdict" for tc in (msg.tool_calls or [])):
            inv.set_status(STATUS_NO_VERDICT)
            write_report(inv)
            print(term.red("The wrap-up call did not render a verdict — hard stop, no further calls. "
                           f"Report: {inv.dir / 'report.md'}"))
            return

        if not msg.tool_calls:
            no_tool_strikes += 1
            if msg.content:
                print(term.dim(f"(agent said: {msg.content[:200]})"))
            if no_tool_strikes >= 3 and inv.budget_remaining() == 0:
                inv.set_status(STATUS_NO_VERDICT)
                write_report(inv)
                print(term.red("Agent never rendered a verdict and the budget is spent — see the report for what was gathered."))
                return
            inv.messages.append({"role": "user", "content":
                                 "[controller] Respond with tool calls only — investigate with a tool, "
                                 "request_more_budget, or finish with render_verdict."})
            inv.save()
            continue
        no_tool_strikes = 0
        investigative = [tc for tc in msg.tool_calls if tc.function.name in IMPLEMENTATIONS]
        single_call_streak = single_call_streak + 1 if len(investigative) == 1 else 0

        concluded = False
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError as exc:
                raw = tc.function.arguments or ""
                if finish == "length":
                    observation = ("ERROR (truncated): your response hit the output-length limit in the middle of these "
                                   f"arguments ({len(raw):,} chars emitted), so the call could not be parsed. " + COMPACT_HINT)
                else:
                    observation = f"ERROR (bad_arguments): could not parse arguments as JSON ({exc}). {COMPACT_HINT}"
                entry = inv.add_log(phase=phase, tool=name, args={"unparseable_arguments_chars": len(raw)},
                                    reasoning=_salvage_reasoning(raw), observation=observation,
                                    api_requests=0, error=_extract_error(observation))
                _stream_step(entry)
                _tool_result(inv, tc.id, name, observation)
                continue

            if concluded:
                _tool_result(inv, tc.id, name, "Investigation already concluded this turn; call skipped.")
                continue

            if name == "render_verdict":
                concluded = _handle_verdict(inv, tc.id, args, phase)
            elif name == "request_more_budget":
                _handle_budget_request(inv, tc.id, args, phase)
            elif name in IMPLEMENTATIONS:
                observation, api_n = dispatch(gh, name, args)
                entry = inv.add_log(phase=phase, tool=name, args=_public_args(args),
                                    reasoning=args.get("reasoning", ""), observation=observation,
                                    api_requests=api_n, error=_extract_error(observation))
                _stream_step(entry)
                _tool_result(inv, tc.id, name, f"[step {entry['id']}]\n{observation}")
            else:
                _tool_result(inv, tc.id, name, f"ERROR (unknown_tool): no tool named '{name}'.")

        # Budget (and, when it matters, GitHub quota) notes ride on the last tool result of the batch —
        # no extra message, no extra tokens wasted.
        if inv.messages[-1].get("role") == "tool":
            inv.messages[-1]["content"] += (f"\n\n[budget: {inv.budget_used()}/{inv.budget_granted()} LLM calls used "
                                            f"— {inv.budget_remaining()} remaining]")
            if single_call_streak >= 3:
                single_call_streak = 0
                inv.messages[-1]["content"] += ("\n[controller: three responses in a row carried a single tool call. "
                                                "Each response costs one budget call regardless of how many tools it "
                                                "invokes — batch independent lookups (several list_commits / get_user "
                                                "at once) into ONE response.]")
            quota = gh.quota() if hasattr(gh, "quota") else {}
            left = quota.get("remaining")
            if not quota.get("authenticated") and isinstance(left, int) and left < 15:
                inv.messages[-1]["content"] += (f"\n[GitHub anonymous quota: {left} requests left, resets "
                                                f"{quota.get('resets_at')} — a rate limit is imminent; spend them on "
                                                "the decisive lookups or conclude on what you have]")
        inv.save()

        if concluded:
            inv.set_status(STATUS_CONCLUDED)
            write_report(inv)
            v = inv.latest_verdict()
            print(f"\n{term.rule('═')}")
            decision = (v.get("decision") or "?").upper().replace("_", " ")
            print(term.bold(term.green(f"VERDICT: {decision}") if v.get("decision") == "adopt"
                            else term.red(f"VERDICT: {decision}") if v.get("decision") == "reject"
                            else term.yellow(f"VERDICT: {decision}")))
            print(v.get("summary", ""))
            print(term.dim(f"Budget: {inv.budget_used()}/{inv.budget_granted()} calls · "
                           f"report: {inv.dir / 'report.md'}"))
            return
