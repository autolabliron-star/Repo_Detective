# DECISIONS

## What went where, and why

**Intake (plain code)** handles everything that does not require judgment: parsing the URL,
collecting the basic repository facts, and sorting out the known failure cases. A 404 or DMCA
response stops the run before any LLM budget is spent. Renamed, archived, or empty repositories do
not stop it; they become findings the agent has to weigh. Intake also prints the GitHub quota,
because the anonymous limit of 60 requests per hour is the main practical constraint of running
without a token.

**The agent** is a custom tool-calling loop, not a framework. The things being evaluated — budget
control, the investigation log, and resuming an investigation — are easier to control directly
than to dig out of a framework.

* **Budget:** one LLM response counts as one call, however many tool calls it batches, so the 30
  calls go further. The counter lives in one place (`llm.py`). Chat questions do not count,
  because the budget applies to the investigation itself; re-tasking does count.

* **Pause and hard stop:** the agent can ask for more budget at any time, and at the latest when
  two calls remain it must either conclude or ask. If the request is denied, it gets one final
  call with access only to `render_verdict`, so it cannot keep investigating past the limit — the
  stop is enforced by the tool set, not by an instruction the model may ignore. The paused state
  is saved, so the same decision can be answered from the CLI or the web UI.

* **Evidence over memory:** the model already knows some of these repositories, so telling it
  not to use memory is not enough. Every evidence item in the verdict must quote the cited
  investigation step verbatim, and the system checks that the quote really appears in the saved
  step. Prior knowledge may suggest what to investigate, never serve as evidence.

* **Senior review:** during testing a fast model closed cases too early. `node-ipc` got "adopt
  with conditions" after three calls even though OSV had already returned malicious-code records.
  Two fixes: the doctrine now says severity first (malicious-code records, then who shipped them,
  then history that does not match the package), and a verdict rendered within the first fifth of
  the budget (six calls of thirty) is handed back once, with the instruction to name every
  suspicious signal it saw and say whether it followed it. It costs one or two calls and produced
  the reject on `node-ipc` and its strongest evidence.

* **Tools take explicit owner/repo values,** so the same tools can investigate the main
  repository, a fork, or any related repository. Tool output surfaces leads — contributor
  concentration, unanswered issues, fork activity — so the agent can see what is worth checking
  next. A file 404 lists the directory, so a `Readme.md` is not mistaken for a missing README
  because of case sensitivity.

* **Lessons from testing:** a 1024-token output cap cut off the verdict JSON and the retry logic
  repeated the request several times; truncation is now detected and the model is asked for a
  shorter answer. GitHub counts `304 Not Modified` responses against the anonymous limit, so a
  one-hour cache protects the quota and ETags only take over after it. Providers differ in what
  they accept for function calling; the client reads the first HTTP 400 and adjusts temperature,
  the token-limit parameter name, forced tool choice, and reasoning effort.

**The chat** has two modes. Q&A receives only the saved investigation log — it has no GitHub
tools — and its `[step N]` citations are checked before the answer is returned, so it answers
from the investigation rather than adding new claims. Re-tasking appends the request to the saved
history and sends the agent back into the same loop with the remaining budget; new verdicts are
saved as v2, v3, and so on.

**The web UI** is the Python standard library and a single HTML file. It reads the same
`state.json` the CLI writes, so both interfaces share one investigation state, and
`docker compose up` brings it up with no extra service. The report is rendered by regular code,
not by the model, so only validated evidence reaches it.

## Cut for time

Server-push streaming of the investigation log to the browser (the page polls every two seconds;
chat answers do stream); GitHub code search (needs authentication); `/stats/contributors`
(asynchronous 202 flow); commit-signature analysis; dependency-tree analysis; caching OSV
responses; package publisher identity — naming the compromised publisher in the `node-ipc` case —
because the APIs I used do not expose npm publishing identities.

## With two more weeks

Recursive dependency analysis ("who else relies on this?"); a simple risk scorecard beside the
written verdict; a direct comparison between a repository and its largest fork; replay of saved
API responses for reliable offline demos; an evaluation suite that runs the three test
repositories regularly and checks both the verdicts and whether the agent followed the important
leads.
