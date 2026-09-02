# DECISIONS

## What went where, and why

**Intake (plain code)** does everything that needs no judgment: URL parsing, the repo facts, the
failure taxonomy. 404/DMCA exit *before* any LLM budget is spent; renames, archived flags, and
empty repos are deliberately **not** exits — they're findings the agent must weigh (an archived
repo is the whole story of `request/request`). Intake also prints the GitHub quota, because the
anonymous limit (60/h) is the real operational risk of a keyless design.

**The agent** is a hand-rolled tool-calling loop — no framework — because the three things that
get graded (budget control, the investigation log, resumability) are exactly the things
frameworks hide. Design choices that matter:

- **Budget unit:** one successful LLM response = 1 call, however many parallel tool calls it
  carries. The prompt encourages batching independent lookups, so the 30 calls go further. The
  counter lives in a single choke point (`llm.py`); chat Q&A passes `budget=None` — the spec
  budgets the *investigation*, and chat is over a finished one. Re-task resumption **does** count.
- **Reserved pitch:** the pause pitch itself costs a call, so at 2 remaining the agent is told to
  conclude or make its case. A denial grants exactly **1 wrap-up call** that mounts *only*
  `render_verdict` (forced tool choice) — you always get a verdict, never a crash or a silent
  overrun, and the stop is mechanical rather than an instruction the model may ignore. The pause
  is persisted state, so it survives Ctrl-C.
- **Two lessons from the first live run.** The healthy baseline (express) ended at 36 calls with no
  verdict. Not budget creep: the agent *had* concluded at call 29, but the verdict JSON — the
  longest thing it ever emits — was cut off by a 1024-token output cap, and our "bad arguments,
  re-issue" feedback made it re-emit the same oversized verdict eight times. Now the cap is
  generous, truncation is detected from `finish_reason`, the failed call is a visible log step,
  and the model is told to *compress*. Second: a case-sensitive 404 (`README.md` vs `Readme.md`)
  became the finding "no README" — so a 404 now lists the directory. Tools must not manufacture
  anomalies.
- **Evidence over memory, mechanically:** the LLM knows these repos' folklore, so prompting
  "don't use memory" isn't enough. Every evidence item must quote the cited step's output
  *verbatim*; a whitespace-normalized substring check rejects anything else and the agent must
  re-cite. Prior knowledge is explicitly allowed for *hypotheses* ("I suspect an incident — find
  it in the data"), which is what makes the logs read like an investigation rather than amnesia.
- **Tools take explicit owner/repo**, so "now check the biggest fork" is the same tools pointed
  at a different repo — no special code path. Trimmers surface leads (contributor share %,
  unanswered-issue summaries, fork freshness) because the agent can only follow what it can see.
- **Rate limits:** an on-disk cache with a 15-minute freshness window (zero requests for repeat
  hits) plus ETag revalidation after it. We *measured* that GitHub now counts 304s against the
  anonymous quota — so freshness short-circuiting, not the ETag folklore, is what actually
  protects the 60/h limit. Mid-run 403 becomes a structured observation the agent reasons about
  ("conclude on what you have, list what's unverified").

**The chat** has two architecturally separate paths: Q&A gets *only* the stored log as context
(GitHub tools aren't mounted), with `[step N]` citations validated; re-tasking appends to the
persisted message history and re-enters the same loop with the remaining budget, appending v2/v3
verdicts rather than overwriting. The report is rendered by plain code so nothing un-cited can
sneak into the final artifact.

## Cut for time

A web UI (the CLI does everything and Dockerizes trivially); GitHub code search (auth-required);
`/stats/contributors` (async-202 dance — `/contributors` gives the bus-factor signal
synchronously); commit-signature and dependency-tree analysis; caching OSV responses.

## With two more weeks

Cross-referencing dependents ("who else relies on this?") and dependency health recursively;
a scorecard-style structured risk model beside the narrative verdict; parallel investigations of
a repo and its top fork with a comparative verdict; replaying stored raw API responses for fully
offline demo runs; richer chat (diffing two verdicts, exporting an ADR); proper eval harness —
run the three test repos nightly and assert the verdicts and the leads followed.
