# The Case of RIAEvangelist/node-ipc

## Verdict: 🛑 REJECT · confidence: high

> Reject. This npm package has verified records of hidden and malicious code, culminating in node-ipc@12.0.1’s obfuscated infostealer payload. The incident report attributes publication to a compromised contributor email with npm write access; the project’s own notice says the owner retained the remaining credential. The named owner, RIAEvangelist, is the dominant contributor and remains active, but the incident report’s final report was still in progress. The repository’s 2023 creation date conflicts with accessible 2021 commit history; its cause could not be established. These findings make publisher trust inadequate for adoption.

**Evidence** (every item mechanically checked against the log):
- ✔ OSV records hidden functionality in node-ipc version 9.2.2.  
  _step 3:_ “Hidden functionality in node-ipc
  affected versions: 9.2.2”
- ✔ OSV records embedded malicious code introduced in version 10.1.1.  
  _step 3:_ “Embedded Malicious Code in node-ipc
  introduced 10.1.1, fixed 10.1.3”
- ✔ OSV records a May 2026 malicious-code advisory affecting version 12.0.1.  
  _step 3:_ “MAL-2026-3744 (GHSA-pvh2-rg5g-69v7) [severity unknown] published 2026-05-14
  Malicious code in node-ipc (npm)
  affected versions: 9.1.6, 9.2.3, 12.0.1”
- ✔ The verified incident report identifies node-ipc@12.0.1 as containing an obfuscated infostealer payload.  
  _step 19:_ “issue #15: [SECURITY][REPORT] node-ipc@12.0.1 CJS bundle contains obfuscated infostealer payload
state: closed (closed 2026-08-21), opened 2026-05-14 by nullcharb, 34 comments, labels: verified”
- ✔ The incident report says the payload exfiltrated data via DNS tunneling.  
  _step 19:_ “This payload is an **infostealer** that harvests system information, environment variables (which often contain secrets/API keys), and sensitive files, then **exfiltrates them via DNS tunneling**.”
- ✔ The project’s historical notice attributes the breach to a contributor with npm write access and says other credentials were revoked.  
  _step 15:_ “there was a breach of a third party server which exposed credentals of a contributor with write access to NPM. All credentials other than mine have now been revoked.”
- ✔ RIAEvangelist is named in the incident investigation and was responsible for the still-in-progress final report.  
  _step 19:_ “|finalize report|↻| @RIAEvangelist |”
- ✔ The repository metadata says it was created in 2023, while accessible commits date to 2021.  
  _step 1:_ “created 2023-01-13, last push 2026-08-24, default branch main”

**Could not be verified:**
- The tools did not identify the specific compromised contributor or npm publisher account, so the individual who shipped the malicious versions could not be named.
- The repository creation date conflicts with accessible 2021 commits, but the tools did not expose migration or reset metadata sufficient to explain the discrepancy.
- No repository-published security advisories were available.

## The Tip-off (intake — plain code, no LLM)

- A nodejs module for local and remote Inter Process Communication (IPC), Neural Networking, and able to facilitate machine learning.
- ⭐ 64 stars · 11 forks · 4 open issues+PRs
- Language: JavaScript · License: MIT
- Created 2023-01-13 · last push 2026-08-24
- Releases: latest release 14.0.0 on 2026-08-24
- Top contributors: RIAEvangelist (72.9%), codex-prime-ai (5.8%), TheWizardNexus (3.7%), Stealthmate (3.2%), Mostafa-Samir (2.6%)

## The Investigation

_One LLM call can batch several tool calls, so step numbers run past the call count; each call is marked below._

<sub>LLM call 1</sub>

**Step 1** · `get_repo{"owner": "RIAEvangelist", "repo": "node-ipc"}`
> 🗒 _The repository was created in 2023 despite a package name with older provenance implied by the case. Establish the repository’s own timeline and status before trusting its surface activity._

```text
RIAEvangelist/node-ipc — A nodejs module for local and remote Inter Process Communication (IPC), Neural Networking, and able to facilitate machine learning.
stars 64, forks 11, open issues+PRs 4
created 2023-01-13, last push 2026-08-24, default branch main
license: MIT, language: JavaScript, size 8,970 KB
archived: False, disabled: False, fork: False
topics: ann, client, ipc, linux, nodejs, posix, server, sockets, tcp, udp
```

**Step 2** · `get_file{"owner": "RIAEvangelist", "repo": "node-ipc", "path": "package.json"}`
> 🗒 _The intake identifies a JavaScript repository but not the published package metadata. Read the manifest to establish package identity, version, and lifecycle scripts._

```text
package.json @ default branch (4,929 chars):
{
  "name": "node-ipc",
  "version": "14.0.0",
  "description": "Fast local and network IPC with Node.js-only JavaScript and aligned dependency-free Rust and C# implementations.",
  "type": "module",
… (105 more lines in the stored log)
```

**Step 3** · `osv_query{"package": "node-ipc", "ecosystem": "npm"}`  ← *following a lead beyond the repo*
> 🗒 _A package with this name warrants an advisory-database check before ordinary maintenance signals. OSV can identify malicious-code records and affected versions._

```text
OSV: 4 known vulnerabilities for npm package 'node-ipc':
- GHSA-3mpp-xfvh-qh37 (no aliases) [LOW] published 2022-03-16
  node-ipc behavior change
  introduced 11.0.0, fixed 12.0.0
- GHSA-8gr3-2gjw-jj7g (no aliases) [LOW] published 2022-03-16
  Hidden functionality in node-ipc
… (7 more lines in the stored log)
```

**Step 4** · `get_security_advisories{"owner": "RIAEvangelist", "repo": "node-ipc"}`
> 🗒 _Repository advisories may document a security incident independently of OSV. Compare the project’s own disclosures with the package database._

```text
no repository-published security advisories. NOTE: maintainers often never publish repo-level advisories even when CVEs exist — cross-check with osv_query using the package name from the manifest (e.g. package.json).
```

**Step 5** · `list_commits{"owner": "RIAEvangelist", "repo": "node-ipc", "per_page": 30}`
> 🗒 _The intake shows a fresh release and a single author holding 72.9% of commits. Inspect the recent commit trail for who is actually shipping changes._

```text
30 commits (no filters, newest first):
- 32dd37232a [2026-08-24] TheWizardNexus: Record UDP transport benchmark results
- 20ef198524 [2026-08-24] TheWizardNexus: Add UDP transport benchmark cohorts
- 4fe3684e21 [2026-08-24] TheWizardNexus: record transport benchmark results
- bf57e88d59 [2026-08-24] TheWizardNexus: benchmark IPC modules by transport
- 0bba23f850 [2026-08-24] TheWizardNexus: Canonicalize packed dependency paths on macOS
… (26 more lines in the stored log)
```

**Step 6** · `get_user{"login": "RIAEvangelist"}`  ← *following a lead beyond the repo*
> 🗒 _One account owns 72.9% of the top-contributor commit total. Profile the dominant maintainer before treating the project as multi-maintainer._

```text
RIAEvangelist (User) — Roshi _ _
account created 2010-08-18, 119 public repos, 248 followers
company: Chief Technology Officer; USAF Veteran, Traditional JavaScript Engineer, AI whisperer, Creator @YouTube, and Mental Health Advocate.
location: Zen Sentry Foundation
```

**Step 7** · `list_issues{"owner": "RIAEvangelist", "repo": "node-ipc", "state": "open", "sort": "updated", "per_page": 20}`
> 🗒 _Only four open issues and PRs are reported. Read the issue queue for unresolved security or maintenance signals behind that small number._

```text
1 open issues, sorted by updated (3 PRs excluded from the issues feed):
- #9 [open] (1 comments, opened 2024-05-09) Increase Buffer Size
summary: 0 of 1 listed issues have 0 comments and no assignee
```

<sub>LLM call 2</sub>

**Step 8** · `list_commits{"owner": "RIAEvangelist", "repo": "node-ipc", "since": "2022-03-01", "until": "2022-04-15", "per_page": 30}`
> 🗒 _OSV records hidden and embedded malicious functionality in March 2022, while this repository begins in 2023. Test whether the relevant history exists here or the repository was reset/recreated._

```text
0 commits returned (since=2022-03-01, until=2022-04-15) — nothing in this window/filter.
```

**Step 9** · `list_commits{"owner": "RIAEvangelist", "repo": "node-ipc", "since": "2026-05-01", "until": "2026-06-15", "per_page": 30}`
> 🗒 _OSV also records malicious code in versions including 12.0.1, published in May 2026. Inspect the repository’s corresponding window for the shipping author and changes._

```text
8 commits (since=2026-05-01, until=2026-06-15, newest first):
- c2d36c8fc9 [2026-05-15] RIAEvangelist: Update README.md bracket inversion
- a602cdc127 [2026-05-15] RIAEvangelist: Update README.md updated to latest commit for v12.0.0
- aea41314fd [2026-05-15] RIAEvangelist: Merge pull request #16 from schneidergithub/master Security commit hash pin info
- f3c4825306 [2026-05-15] schneidergithub: Update README with security breach information
- 25326e8d6a [2026-05-15] schneidergithub: Update README with security recommendations
… (3 more lines in the stored log)
```

**Step 10** · `get_user{"login": "TheWizardNexus"}`  ← *following a lead beyond the repo*
> 🗒 _The latest release trail is authored by TheWizardNexus rather than the dominant historical contributor. Establish whether this is an accountable, established maintainer._

```text
TheWizardNexus (User) — The Wizard Nexus
account created 2026-07-13, 7 public repos, 2 followers
company: TheWizardNexus
```

**Step 11** · `get_user{"login": "codex-prime-ai"}`  ← *following a lead beyond the repo*
> 🗒 _The second recent release author is codex-prime-ai. Profile this account because it made a concentrated set of release-adjacent changes._

```text
codex-prime-ai (User) — no display name
account created 2025-10-10, 1 public repos, 2 followers
```

**Step 12** · `get_file{"owner": "RIAEvangelist", "repo": "node-ipc", "path": "SECURITY.md"}`
> 🗒 _The manifest ships SECURITY.md despite no repository advisories. Read the project’s stated vulnerability-reporting and remediation posture._

```text
SECURITY.md @ default branch (6,332 chars):
# Security Policy

## Supported Versions

| Version | Supported          |
… (79 more lines in the stored log)
```

**Step 13** · `list_releases{"owner": "RIAEvangelist", "repo": "node-ipc"}`
> 🗒 _The current manifest is 14.0.0, but OSV names malicious historical versions. Obtain the release/tag chronology to see whether remediation is traceable in this repository._

```text
3 most recent GitHub releases:
- 14.0.0 "14.0.0" published 2026-08-24
- 12.0.0 "12.0.0" published 2024-08-13
- 10.1.0 "10.1.0" published 2023-01-18
```

<sub>LLM call 3</sub>

**Step 14** · `get_commit{"owner": "RIAEvangelist", "repo": "node-ipc", "sha": "f3c4825306"}`
> 🗒 _The May 2026 window contains a commit explicitly titled security breach information. Inspect its author, exact content, and whether it identifies the malicious release and remediation._

```text
commit f3c4825306 by schneidergithub on 2026-05-15
message: Update README with security breach information

Added a note about security recommendations and version pinning.
stats: 1 files changed, +1 -0

… (9 more lines in the stored log)
```

**Step 15** · `get_file{"owner": "RIAEvangelist", "repo": "node-ipc", "path": "README.md", "ref": "f3c4825306"}`
> 🗒 _The breach-information commit changed README documentation. Read the resulting historical notice to identify the incident’s stated scope and attribution._

```text
README.md @ f3c4825306 (31,391 chars):
node-ipc
================

[![Sponsor RIAEvangelist to help development of node-ipc](https://img.shields.io/static/v1?label=Sponsor%20Me%20On%20Github&message=%E2%9D%A4&logo=GitHub&link=https://github.com/sponsors/RIAEvangelist)](https://github.com/sponsors/RIAEvangelist)

… (96 more lines in the stored log)
```

**Step 16** · `get_user{"login": "schneidergithub"}`  ← *following a lead beyond the repo*
> 🗒 _The breach-information commit was authored by schneidergithub, not the owner. Profile the reporter/contributor to distinguish disclosure from the party who shipped the package._

```text
schneidergithub (User) — Aaron Schneider
account created 2021-09-05, 30 public repos, 36 followers
```

**Step 17** · `list_commits{"owner": "RIAEvangelist", "repo": "node-ipc", "author": "RIAEvangelist", "per_page": 30}`
> 🗒 _The owner authored the May breach-response commits and dominates historical contributions. Review their recent repository activity to determine whether they remained the release authority after the incident._

```text
30 commits (author=RIAEvangelist, newest first):
- 848af4cd56 [2026-08-17] RIAEvangelist: Modernize Node.js CI matrix
- c2d36c8fc9 [2026-05-15] RIAEvangelist: Update README.md bracket inversion
- a602cdc127 [2026-05-15] RIAEvangelist: Update README.md updated to latest commit for v12.0.0
- aea41314fd [2026-05-15] RIAEvangelist: Merge pull request #16 from schneidergithub/master Security commit hash pin info
- 2843bdefb8 [2026-05-15] RIAEvangelist: Update README.md security release info typo
… (26 more lines in the stored log)
```

<sub>LLM call 4</sub>

**Step 18** · `render_verdict{"decision": "reject"}`
> 🗒 _OSV establishes repeated malicious-code records, and the repository’s historical README confirms a 2026 credential breach involving npm write access. That is decisive: render the verdict rather than mistake version pinning for a cure to publisher compromise._

```text
SENIOR REVIEW: verdict (reject) handed back for a second look after 4 call(s) — anomalies must be pursued or explicitly closed before concluding
```

<sub>LLM call 5</sub>

**Step 19** · `get_issue{"owner": "RIAEvangelist", "repo": "node-ipc", "number": 15}`
> 🗒 _The historical breach notice directs readers to issue #15. Read the incident discussion for attribution, remediation, and whether the compromised publisher is named._

```text
issue #15: [SECURITY][REPORT] node-ipc@12.0.1 CJS bundle contains obfuscated infostealer payload
state: closed (closed 2026-08-21), opened 2026-05-14 by nullcharb, 34 comments, labels: verified
body: **issue fixed by NPM valid report will be made for public notice**

|task|status|contributor|
|----|-------|------------|
… (49 more lines in the stored log)
```

**Step 20** · `get_commit{"owner": "RIAEvangelist", "repo": "node-ipc", "sha": "a98efaedbf"}`
> 🗒 _The breach notice recommends commit a98efaedbf as the safe reference. Inspect its code diff and authorship to establish what the owner shipped after the incident._

```text
commit a98efaedbf by RIAEvangelist on 2024-08-12
message: with the conflict now being a fullscale war with both sides invading eachother everyone should pray for peace and one day there being no more war. This update pushes the v10.1.0 version and secuity updates to the clean v12.0.0 version for even those that are still using * or latest for their dependancies. closes #3
stats: 43 files changed, +222 -221

--- coverage/lcov.info (+75 -75, modified)
@@ -1,21 +1,21 @@
… (677 more lines in the stored log)
```

**Step 21** · `get_user_events{"login": "RIAEvangelist"}`  ← *following a lead beyond the repo*
> 🗒 _The owner retained the only stated npm credential after the breach and dominates repository history. Check whether the named maintainer remains publicly active now._

```text
28 recent public events for RIAEvangelist, from 2026-08-24 to 2026-09-02: ReleaseEvent×21, PushEvent×3, CreateEvent×2, DeleteEvent×1, MemberEvent×1
most recent: ReleaseEvent on TheWizardNexus/arcane-os-sdk at 2026-09-02
NOTE: GitHub serves only ~90 days / 300 events of public activity — silence here does not prove long-term inactivity; use list_commits(author=...) for a durable timeline.
```

**Step 22** · `list_commits{"owner": "RIAEvangelist", "repo": "node-ipc", "until": "2023-01-14", "per_page": 30}`
> 🗒 _The repository metadata says it was created in 2023, yet the commit log reaches 2021. Retrieve the oldest accessible window to characterize whether this is imported history rather than a reset._

```text
30 commits (until=2023-01-14, newest first):
- b78969d045 [2021-12-10] RIAEvangelist: Added sponsor badge
- 9bbd515473 [2021-12-08] RIAEvangelist: clarifying v10+ includes
- 6f265d9cb0 [2021-12-07] RIAEvangelist: clarified es6 vs commonjs import
- 7a614ce9be [2021-09-15] RIAEvangelist: Merge pull request #219 from tripodsgames/cjs
- 083546305f [2021-09-15] tripodsgames: Fix ESM and Commonjs compatibility.
… (26 more lines in the stored log)
```

**Step 23** · `list_issues{"owner": "RIAEvangelist", "repo": "node-ipc", "state": "all", "sort": "created", "per_page": 20}`
> 🗒 _The current open issue is not security-related, but the breach issue may be closed or absent from the recent feed. Survey all accessible issues for unresolved incident reports and maintainer responses._

```text
5 all issues, sorted by created (8 PRs excluded from the issues feed):
- #15 [closed] (34 comments, opened 2026-05-14) [SECURITY][REPORT] node-ipc@12.0.1 CJS bundle contains obfuscated infostealer payload
- #10 [closed] (1 comments, opened 2024-08-23) Can the latest version 12.0.0 of node-ipc be installed using npm install?
- #9 [open] (1 comments, opened 2024-05-09) Increase Buffer Size
- #6 [closed] (2 comments, opened 2023-08-16) Add emit(value: any) definition for when using raw buffer
- #3 [closed] (14 comments, opened 2023-02-22) ‎ 
… (1 more lines in the stored log)
```

**Step 24** · `get_commit{"owner": "RIAEvangelist", "repo": "node-ipc", "sha": "848af4cd56"}`
> 🗒 _The owner made a post-incident August 2026 CI change. Inspect the latest owner-authored commit to see whether current release governance or package behavior was altered._

```text
commit 848af4cd56 by RIAEvangelist on 2026-08-17
message: Modernize Node.js CI matrix
stats: 1 files changed, +0 -23

--- .github/workflows/node.js.yml (+0 -23, modified)
@@ -35,26 +35,3 @@ jobs:
… (26 more lines in the stored log)
```

<sub>LLM call 6</sub>

**Step 25** · `render_verdict{"decision": "reject"}`
> 🗒 _The incident has now been pursued to the named owner, the affected version, payload behavior, and stated credential outcome. The remaining history anomaly is documented as unresolved; the verified malicious release independently decides the case._

```text
verdict v1 recorded: reject
```

## Budget ledger

- Initial budget: 30 LLM calls · used: 6 · remaining: 24
- 25 investigation steps in 6 LLM calls (a call that batches N tool calls produces N steps but costs 1)

---
_Generated 2026-09-02 07:55 UTC · every evidence item cites an investigation step; anything that couldn't be verified is labeled as such._
