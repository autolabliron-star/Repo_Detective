# Example case files

The three repositories the assignment grades against, as investigated on 2026-09-02 with a
30-call budget and no extensions. Each directory holds the rendered `report.md` (plain code from
`state.json`) and the full `state.json` — investigation log, budget ledger, verdict history, and
the exact message history the agent saw.

| Case | Verdict | LLM calls | Steps |
|---|---|---|---|
| [expressjs/express](expressjs__express/report.md) | ✅ adopt · high | 5 | 24 |
| [request/request](request__request/report.md) | 🛑 reject · high (v1 at 4 calls; v2 unchanged after the re-task "now check the biggest fork") | 9 | 41 |
| [RIAEvangelist/node-ipc](riaevangelist__node-ipc/report.md) | 🛑 reject · high | 6 | 25 |

Verdicts are dated. The agent reads live data, so a run on another day can differ: on the evening of
2026-09-02 two new advisories on express's `qs` dependency (CVE-2026-82417 and CVE-2026-82562, both
fixed in qs 6.16.0) moved express from *adopt* to *adopt with conditions*. That is the point — the
verdict follows what the API returns on the day, not the repository's reputation. Nothing in the
code reads this folder.

Read node-ipc's log for the shape of a real investigation: OSV's malicious-code records → an
empty commit window in March 2022 (the repository was recreated) → the May 2026 breach commit →
the historical README at that commit → the verified infostealer issue → the owner's profile and
activity — with the senior review handing back a first verdict at call 4 and the second look
producing the strongest evidence.
