# 🔍 The Repo Detective

An AI agent that investigates any public GitHub repository the way a security analyst would —
deciding for itself what to check, following the leads it finds, and finishing with an
evidence-backed verdict: **adopt** / **adopt with conditions** / **reject**.

## Quickstart (Docker, ~2 minutes)

```bash
cp .env.example .env      # your LLM API key + model — the only required setup
docker compose up         # → open http://localhost:8000
```

- **Running all three test repositories within one hour?** Add a free `GITHUB_TOKEN` (no scopes)
  to `.env`. GitHub allows 60 anonymous API requests per hour and one investigation uses 25–45,
  so without a token the third run hits the limit — the agent then concludes on what it could
  verify and says what it couldn't (see *Grace under fire*). The token is optional; nothing else
  needs an account.
- **Port 8000 taken?** `DETECTIVE_PORT=8001 docker compose up`
- **Local model (Ollama, vLLM, LM Studio)?** From inside Docker the host is
  `host.docker.internal`, not `localhost` — e.g. `OPENAI_BASE_URL=http://host.docker.internal:11434/v1`.

The web UI is where you investigate a repository, watch the log grow live, approve or deny the
agent's budget requests, read the case file, and chat with it. The same case files are one
command away in the terminal:

```bash
docker compose run --rm detective investigate https://github.com/expressjs/express   # one command to investigate
docker compose run --rm detective chat expressjs/express                              # one to start the chat
docker compose run --rm detective list
```

Works with **any OpenAI-compatible provider**: set `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and
`OPENAI_MODEL` in `.env` — no vendor or model is hardcoded. The client adapts at runtime to what
the provider accepts (temperature, `max_tokens` vs `max_completion_tokens`, forced tool choice,
`reasoning_effort`), so switching providers is configuration, not code. No other keys or accounts
are needed.

| Provider | `OPENAI_BASE_URL` | `OPENAI_MODEL` |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | any model with tool calling |
| Anthropic | `https://api.anthropic.com/v1` | any Claude model id, e.g. `claude-sonnet-5` |
| Azure OpenAI | `https://<resource>.openai.azure.com/openai/v1` | your deployment name |
| Local (Ollama, vLLM, LM Studio) | `http://host.docker.internal:<port>/v1` | the model you serve; the key can be any non-empty string |

The agent needs a model that supports function calling; that is the only requirement. Every
provider-specific parameter difference is learned from the endpoint's first error and adapted,
not hardcoded. The stored example runs were produced through an OpenAI-compatible gateway serving
a GPT-5 family model.

### Running without Docker

```bash
pip install -r requirements.txt
python -m detective serve                      # web UI on :8000
python -m detective investigate request/request
python -m detective chat request/request
```

## What happens in an investigation

1. **Intake (plain code, no LLM).** Fetches the basic facts — name, stars, last release, top
   contributors — and handles the ugly cases up front: 404s and DMCA takedowns exit cleanly;
   renames, archived flags, and empty repos become *findings* handed to the agent.
2. **The agent.** A hand-rolled tool-calling loop over the GitHub REST API (commits,
   contributors, issues, PRs, releases, files, forks, advisories, user activity) plus the OSV
   vulnerability database. There is no checklist: after each step it reads what came back and
   picks the next move — one person wrote most of the code? It checks what that person has been
   doing. Issues piling up unanswered? It checks whether the community moved to a fork. A
   malicious-code record in OSV? That becomes the investigation: which versions, who shipped
   them, what happened afterwards.
   - **Budget: 30 LLM calls, hard stop.** One assistant response = one call, however many tool
     calls it batches, so step numbers run past the call count; the log marks every call. When
     the budget runs out — or the agent decides it can't conclude — it pauses and pitches the
     human: what it has, what it still needs, how many calls. You approve, adjust, or deny
     (denial grants exactly one wrap-up call, which can only render a verdict).
   - **Senior review.** A verdict rendered after only a handful of calls is handed back once:
     name every anomaly you saw and say whether you pursued it. Cheap, mechanical, and it is what
     turned a hasty "adopt with conditions" on a package with malicious-code history into a
     reject built on the incident's own paper trail.
   - **Every step is logged** — what it did, why, and what it found — and streamed live.
3. **The verdict + report.** `render_verdict` is validated mechanically: every evidence item must
   quote the cited step's output *verbatim* (elisions with "..." allowed when each fragment is
   verbatim and in order), or the call is rejected and the agent must re-cite. The LLM may know
   these repos' folklore; the verdict can only be built from what the tools actually returned.
   A case-file report is rendered by plain code to `investigations/<slug>/report.md`.

## The chat

```
you> why did you flag the maintainer situation?
```
Answered **from the stored log** — the Q&A path doesn't even have GitHub tools mounted — with
`[step N]` citations validated against the log. If it wasn't investigated, it says so. Answers
stream word by word as the model writes them, in the terminal and in the web UI alike.

```
you> now check the biggest fork
```
Re-tasking appends the directive to the same conversation and resumes the agent loop with the
**remaining budget**. If the new evidence warrants it, the verdict is revised (v2, with an
explicit "what changed"). In the terminal: `/report`, `/log`, `/budget`, `/quit`.

## Grace under fire

Renamed repos are followed to their canonical name (and logged). 404 / DMCA exit with a clear
message before any budget is spent. Empty repos, archived repos, and rate limits become structured
observations the agent reasons about — the report says what *couldn't* be verified instead of
inventing it. File paths are case-sensitive on GitHub, so a 404 from a file read lists the
directory rather than letting the agent conclude a README is "missing".

Rate limits: intake shows the quota and warns when it won't cover a run; the agent is told when a
limit is imminent; a mid-run 403 becomes an observation. The client also keeps an on-disk response
cache: within a one-hour freshness window (`DETECTIVE_CACHE_TTL`) repeat requests cost **zero**
quota, and after it ETag revalidation keeps the cache correct.

## Repo layout

```
detective/
  intake.py           plain-code intake (no LLM)
  agent.py            the investigation loop: budget, pause-and-ask, senior review, resume
  llm.py              OpenAI-compatible client — the single budget choke point
  github_client.py    freshness cache + ETag, rate-limit telemetry, structured errors
  tools/registry.py   tool schemas + dispatch (every tool logs its reasoning)
  tools/github.py     GitHub tools with lead-surfacing trimmers
  tools/osv.py        OSV vulnerability queries
  validator.py        mechanical evidence-citation validation
  investigation.py    state.json: log, budget ledger, verdict history
  report.py           plain-code case-file renderer
  chat.py             grounded Q&A + re-tasking
  web.py, static/     the web UI (standard library only; one HTML file)
investigations/       one directory per case: state.json, report.md
examples/             case files from the three test repositories, as investigated
```

## Tests

```bash
pip install -r requirements.txt && python -m unittest discover -s tests -v
# or without installing anything:
docker compose run --rm -v ./tests:/app/tests --entrypoint python detective -m unittest discover -s tests
```

Covers the budget invariants (used ≤ granted, exhaustion raises, denial grants exactly one
wrap-up call and can't creep), the evidence validator (fabricated quotes rejected, elisions
accepted), the agent loop end-to-end with a scripted LLM (truncated verdicts, senior review,
web-side budget approval), the LLM client's provider adaptations, the tool trimmers, the web API,
and URL parsing.

## Design decisions

See [DECISIONS.md](DECISIONS.md).

## License

MIT — see [LICENSE](LICENSE).
