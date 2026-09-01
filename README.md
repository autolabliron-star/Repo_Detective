# 🔍 The Repo Detective

An AI agent that investigates any public GitHub repository the way a security analyst would —
deciding for itself what to check, following the leads it finds, and finishing with an
evidence-backed verdict: **adopt** / **adopt with conditions** / **reject**.

## Quickstart (Docker, ~2 minutes)

```bash
cp .env.example .env      # put your LLM API key + model in it (the only setup)
docker compose build

# one command to investigate a repo:
docker compose run --rm detective investigate https://github.com/expressjs/express

# one command to start the chat over the finished investigation:
docker compose run --rm detective chat expressjs/express
```

> Use `docker compose run` (not `up`) — the agent pauses to ask a human for budget approval,
> which needs an interactive terminal. `run` allocates one; `up` just prints usage.

Works with **any OpenAI-compatible provider**: set `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and
`OPENAI_MODEL` in `.env` — no vendor or model is hardcoded. No other keys or accounts are
needed (an optional `GITHUB_TOKEN` raises the GitHub rate limit, but everything runs without it).

### Running without Docker

```bash
pip install -r requirements.txt
python -m detective investigate https://github.com/request/request
python -m detective chat request/request
python -m detective list
```

## What happens in an investigation

1. **Intake (plain code, no LLM).** Fetches the basic facts — name, stars, last release, top
   contributors — and handles the ugly cases up front: 404s and DMCA takedowns exit cleanly;
   renames, archived flags, and empty repos become *findings* handed to the agent.
2. **The agent.** A hand-rolled tool-calling loop over the GitHub REST API (commits,
   contributors, issues, PRs, releases, files, forks, advisories, user activity) plus the OSV
   vulnerability database. There is no checklist: after each step it reads what came back and
   picks the next move — one person wrote 95% of the code? It checks what's happening with that
   person. Issues piling up unanswered? It checks whether the community moved to a fork.
   - **Budget: 30 LLM calls, hard stop.** One assistant response = one call, however many
     tool calls it batches. When the budget runs out — or the agent decides it can't conclude —
     it pauses and pitches the human: what it has, what it still needs, how many calls. You
     approve, adjust, or deny (denial grants exactly one wrap-up call so you always get a verdict).
   - **Every step is logged** — what it did, why, and what it found — and streamed live.
3. **The verdict + report.** `render_verdict` is validated mechanically: every evidence item must
   quote the cited step's output *verbatim*, or the call is rejected and the agent must re-cite.
   The LLM may know these repos' folklore; the verdict can only be built from what the tools
   actually returned. A readable case-file report is rendered by plain code to
   `investigations/<slug>/report.md`.

## The chat

```
you> why did you flag the maintainer situation?
```
Answered **from the stored log** — the Q&A path doesn't even have GitHub tools mounted — with
`[step N]` citations validated against the log. If it wasn't investigated, it says so.

```
you> now check the biggest fork
```
Re-tasking appends the directive to the same conversation and resumes the agent loop with the
**remaining budget**. If the new evidence warrants it, the verdict is revised (v2, with an
explicit "what changed"). Commands: `/report`, `/log`, `/budget`, `/quit`.

## Grace under fire

Renamed repos are followed to their canonical name (and logged). 404 / DMCA exit with a clear
message. Empty repos, archived repos, and rate limits become structured observations the agent
reasons about — the report says what *couldn't* be verified instead of inventing it.

GitHub's anonymous quota is 60 requests/hour. The client keeps an on-disk response cache: within
a 15-minute freshness window (`DETECTIVE_CACHE_TTL`) repeat requests cost **zero** quota, and
after it ETag revalidation keeps the cache correct — so re-running the same repos barely consumes
quota. The current quota is shown at intake, and a mid-run rate limit becomes an observation the
agent reasons about rather than a crash.

## Repo layout

```
detective/
  intake.py           plain-code intake (no LLM)
  agent.py            the investigation loop: budget, pause-and-ask, resume
  llm.py              OpenAI-compatible client — the single budget choke point
  github_client.py    ETag cache, rate-limit telemetry, structured errors
  tools/registry.py   tool schemas + dispatch (every tool logs its reasoning)
  tools/github.py     GitHub tools with lead-surfacing trimmers
  tools/osv.py        OSV vulnerability queries
  validator.py        mechanical evidence-citation validation
  investigation.py    state.json: log, budget ledger, verdict history
  report.py           plain-code case-file renderer
  chat.py             grounded Q&A + re-tasking
investigations/       one directory per case: state.json, report.md
```

## Tests

```bash
python -m unittest discover -s tests -v
```

Covers the budget invariants (used ≤ granted, exhaustion raises, denial grants one wrap-up
call), the evidence validator (fabricated quotes rejected), and URL parsing.

## Design decisions

See [DECISIONS.md](DECISIONS.md).
