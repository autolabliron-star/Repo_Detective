# DECISIONS

## What went where, and why

**Intake (plain code)** does everything that needs no judgment: URL parsing, the repo facts, the
failure taxonomy. 404/DMCA exit *before* any LLM budget is spent; renames, archived flags, and
empty repos are deliberately **not** exits — they're findings the agent must weigh. Intake also
prints the GitHub quota, because the anonymous limit (60/h) is the real operational risk of a
keyless design.

**The agent** is a hand-rolled tool-calling loop — no framework — because the things that get
graded (budget control, the investigation log, resumability) are exactly what frameworks hide.

- **Budget unit:** one LLM response = 1 call, however many tool calls it batches, so 30 calls go
  further. The counter lives in one choke point (`llm.py`); chat Q&A is uncounted (the spec
  budgets the *investigation*); re-task resumption counts.
- **Pause and hard stop, mechanically.** At 2 remaining the agent is told to conclude or pitch.
  A denial grants one wrap-up call that mounts *only* `render_verdict`, so the budget cannot
  creep — a stop enforced by the tool set, not by an instruction the model may ignore. The
  pause is persisted state; the terminal and the web UI are two channels for the same decision.
- **Evidence over memory, mechanically.** The model knows these repos' folklore, so "don't use
  memory" isn't enough: every evidence item must quote its step *verbatim* ("..." elisions
  allowed if each fragment is verbatim and in order), checked by substring. Prior knowledge is
  allowed for *hypotheses* — that is what makes the logs read like an investigation, not amnesia.
- **Senior review.** Live runs showed a fast model closing early: node-ipc got "adopt with
  conditions" in 3 calls with OSV's malicious-code records on screen. Doctrine now says severity
  first (malicious code → who shipped it → history that doesn't match the package), and a verdict
  rendered after ≤ a fifth of the budget is handed back once: name each anomaly, say whether you
  pursued it. Cost 1–2 calls; it produced the reject and its strongest evidence.
- **Tools take explicit owner/repo**, so "check the biggest fork" is the same tools pointed at
  another repo. Trimmers surface leads (contributor share %, unanswered-issue summary, fork
  freshness) because the agent can only follow what it can see; a file 404 lists the directory
  so a case-sensitive `Readme.md` never becomes "no README".
- **Lessons the live runs taught.** A 1024-token output cap truncated the verdict JSON and our
  "re-issue" feedback looped it eight times — now truncation is detected and the model is told
  to compress. GitHub counts 304 revalidations against the anonymous quota, so a one-hour
  freshness cache, not ETags, protects the limit. The provider we tested requires
  `reasoning_effort="none"` for function tools — the client learns provider quirks from the
  first 400 and adapts (temperature, token-cap name, forced tool choice, reasoning effort).

**The chat** has two separate paths: Q&A sees *only* the stored log (GitHub tools aren't
mounted) and its `[step N]` citations are validated; re-tasking appends to the persisted history
and re-enters the same loop with the remaining budget, appending v2/v3 verdicts. **The web UI**
is standard library only — one HTML file polling the same `state.json` the CLI writes — so
`docker compose up` brings everything up with no extra dependency, and the report is still
rendered by plain code so nothing un-cited can sneak into the artifact.

## Cut for time

Pushing the investigation log to the browser live (the page polls every 2 s; chat answers do stream); GitHub code search
(auth-required); `/stats/contributors` (async-202 dance); commit-signature and dependency-tree
analysis; caching OSV responses; naming the compromised publisher in node-ipc (the API doesn't
expose npm publish identities).

## With two more weeks

Dependents and dependency health recursively ("who else relies on this?"); a scorecard-style
risk model beside the narrative; comparative investigation of a repo and its top fork; replaying
stored API responses for offline demos; an eval harness that runs the three test repos nightly
and asserts the verdicts *and* the leads followed.
