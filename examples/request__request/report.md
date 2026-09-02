# The Case of request/request

## Verdict: 🛑 REJECT · confidence: high · v2, revised after re-task: “now check the biggest fork”

> Reject request/request unchanged. All raised anomalies were pursued: OSV returned no malicious-code record; Mikeal authored and committed the original project’s full-deprecation notice; SzymonDrosdzol of Doyensec reported the unanswered SSRF disclosure; and the largest fork was confirmed as an active, separately named Postman package with a security patch incorporated in its July 2026 version bump. That fork does not change the requested package’s status: request itself remains retired, unmaintained since 2020, and recorded by OSV with an SSRF vulnerability for which no fix is listed.

**What changed since the previous verdict:** The decision remains reject. The additional investigation confirms that the largest fork is active and separately versioned, but it also confirms the original project’s retirement was deliberately committed by Mikeal and does not resolve request’s recorded unfixed SSRF vulnerability or its absence of merged maintenance since 2020.

**Evidence** (every item mechanically checked against the log):
- ✔ Mikeal authored the original repository’s full-deprecation commit.  
  _step 36:_ “commit aded7e4f8e by mikeal on 2020-02-11
message: doc: note full deprecation (#3267)”
- ✔ That retirement commit adds the statement that request is fully deprecated and no new changes are expected.  
  _step 36:_ “As of Feb 11th 2020, request is fully deprecated. No new changes are expected land.”
- ✔ OSV records an SSRF vulnerability for request with no fix listed.  
  _step 4:_ “Server-Side Request Forgery in Request
  introduced 0, no fix listed”
- ✔ The SSRF report says direct emails to the maintainer received no answer.  
  _step 10:_ “we have received no answer.”
- ✔ The named SSRF reporter is associated with Doyensec.  
  _step 40:_ “SzymonDrosdzol (User) ... company: Doyensec”
- ✔ The original repository’s PR history reports its most recent merge was in 2020.  
  _step 8:_ “summary: 1 of 20 listed PRs were merged; most recent merge 2020-02-11”
- ✔ The biggest fork is separately published as postman-request.  
  _step 23:_ “"name": "postman-request" ... "version": "2.88.1-postman.49"”
- ✔ The fork’s security patch was followed the same day by a version bump to 2.88.1-postman.49.  
  _step 37:_ “commit 02741a5589 by appurva21 on 2026-07-21
message: 2.88.1-postman.49”

**Could not be verified:**
- OSV returned no malicious-code or hidden-functionality record for request, but this investigation did not inspect npm tarballs or registry publisher identities.
- The largest fork was not fully assessed as a replacement: release-to-registry publication linkage and specific remediation of CVE-2023-28155 were not verified.

### Verdict history
- v1 — 🛑 REJECT (initial, at 4 calls used)
- v2 — 🛑 REJECT (retask: now check the biggest fork, at 9 calls used)

## The Tip-off (intake — plain code, no LLM)

- 🏊🏾 Simplified HTTP request client.
- ⭐ 25,511 stars · 3,142 forks · 143 open issues+PRs
- Language: JavaScript · License: Apache-2.0
- Created 2011-01-23 · last push 2024-08-14
- Releases: no GitHub releases, but tags exist (latest tag: v2.88.1)
- Top contributors: mikeal (35.2%), simov (26.9%), nylen (17.0%), greenkeeperio-bot (2.8%), seanstrom (2.6%)

## The Investigation

_One LLM call can batch several tool calls, so step numbers run past the call count; each call is marked below._

<sub>LLM call 1</sub>

**Step 1** · `get_repo{"owner": "request", "repo": "request"}`
> 🗒 _The intake shows an old, popular package with a 2024 push but no GitHub release. Establish the repository’s own status and any deprecation signal before treating activity as maintenance._

```text
request/request — 🏊🏾 Simplified HTTP request client.
stars 25,511, forks 3,142, open issues+PRs 143
created 2011-01-23, last push 2024-08-14, default branch master
license: Apache-2.0, language: JavaScript, size 2,290 KB
archived: False, disabled: False, fork: False
```

**Step 2** · `get_file{"owner": "request", "repo": "request", "path": "README.md"}`
> 🗒 _A package this old may announce retirement in its README. Read the maintainer’s notice rather than infer intent from timestamps._

```text
README.md @ default branch (46,374 chars):
# Deprecated!

As of Feb 11th 2020, request is fully deprecated. No new changes are expected to land. In fact, none have landed for some time.

For more information about why request is deprecated and possible alternatives refer to
… (155 more lines in the stored log)
```

**Step 3** · `get_file{"owner": "request", "repo": "request", "path": "package.json"}`
> 🗒 _The intake identifies JavaScript but not the published identity or current version. The manifest anchors the OSV query to the actual package._

```text
package.json @ default branch (1,938 chars):
{
 "name": "request",
 "description": "Simplified HTTP request client.",
 "keywords": [
  "http",
… (81 more lines in the stored log)
```

**Step 4** · `osv_query{"package": "request", "ecosystem": "npm"}`  ← *following a lead beyond the repo*
> 🗒 _This is a widely consumed npm package; query the vulnerability record directly, with special attention to malicious-code classifications._

```text
OSV: 2 known vulnerabilities for npm package 'request':
- GHSA-7xfp-9c55-5vqj (CVE-2017-16026) [CVSS3 CVSS:3.0/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N] published 2018-11-09
  Remote Memory Exposure in request
  introduced 2.49.0, fixed 2.68.0; introduced 2.2.6, fixed 2.68.0
- GHSA-p8p7-x288-28g6 (CVE-2023-28155) [CVSS3 CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N] published 2023-03-16
  Server-Side Request Forgery in Request
… (1 more lines in the stored log)
```

**Step 5** · `get_security_advisories{"owner": "request", "repo": "request"}`
> 🗒 _Repository advisories can reveal maintainer-recognized incidents that a package-only query may not contextualize._

```text
no repository-published security advisories. NOTE: maintainers often never publish repo-level advisories even when CVEs exist — cross-check with osv_query using the package name from the manifest (e.g. package.json).
```

**Step 6** · `list_commits{"owner": "request", "repo": "request", "per_page": 30}`
> 🗒 _The 2024 push could be a substantive maintenance event or mere metadata. Inspect the recent commit timeline and authorship._

```text
30 commits (no filters, newest first):
- 3c0cddc7c8 [2020-02-11] gr2m: README: typo in deprecation message (#3268)
- aded7e4f8e [2020-02-11] mikeal: doc: note full deprecation (#3267)
- 212570b697 [2019-05-29] andresroberto: Use nyc instead of istanbul (#3169)
- b3a218dc7b [2019-04-04] odykyi: Update README.md (#3023)
- b0e9abb2f2 [2019-04-01] shige: docs: :memo: Updated the Change Log for v2.88.0 (2018/08/10) (#3008)
… (26 more lines in the stored log)
```

**Step 7** · `list_issues{"owner": "request", "repo": "request", "state": "open", "sort": "updated", "per_page": 20}`
> 🗒 _Open issue volume alone is noise; recent updated issues and replies show whether anyone is still tending the project._

```text
20 open issues, sorted by updated (2 PRs excluded from the issues feed):
- #3752 [open] (5 comments, opened 2025-09-12) Announcing dropin-request: A Drop-In Replacement for request
- #3143 [open] (106 comments, opened 2019-04-01) Alternative libraries to request
- #3480 [open] (2 comments, opened 2023-12-29) Docs on migrating from request to fetch?
- #3759 [open] (0 comments, opened 2026-04-13) naraa
- #3758 [open] (0 comments, opened 2026-03-11) Access to raise new issue for (Allegis Use Only) Contractor Onboarding/Extension Request.
… (16 more lines in the stored log)
```

**Step 8** · `list_pulls{"owner": "request", "repo": "request", "state": "all", "per_page": 20}`
> 🗒 _Merged PR recency is the clearest test of active stewardship, especially where commits may be automated._

```text
20 all PRs (most recently updated first):
- #3757 [closed] Revise security policy and vulnerability reporting (by Loulou823)
- #3268 [merged 2020-02-11] README: typo in deprecation message (by gr2m)
- #3749 [closed] feat: add support for SOCKS proxy (by appurva21)
- #3508 [closed] Added SASVA suggested fixes for CVE-2023-28155 (by damithn)
- #3491 [closed] Http signature (by sreenijakurremula)
… (16 more lines in the stored log)
```

<sub>LLM call 2</sub>

**Step 9** · `render_verdict{"decision": "reject"}`
> 🗒 _The repository’s own README declares retirement, OSV records an unfixed SSRF vulnerability, and no PR has merged since the retirement notice. This is abandonment with a known unresolved security defect, not ordinary dependency hygiene._

```text
SENIOR REVIEW: verdict (reject) handed back for a second look after 2 call(s) — anomalies must be pursued or explicitly closed before concluding
```

<sub>LLM call 3</sub>

**Step 10** · `get_issue{"owner": "request", "repo": "request", "number": 3442}`
> 🗒 _OSV identifies an unfixed SSRF and the issue list shows a dedicated report. Read the report and discussion to establish whether maintainers addressed it or left it unresolved._

```text
issue #3442: CVE-2023-28155 Request allows a bypass of SSRF mitigations via an attacker-controller server that does a cross-protocol redirect
state: open, opened 2023-03-08 by SzymonDrosdzol, 8 comments, labels: none
body: ### Summary
I am a security researcher at [Doyensec](https://doyensec.com/).

During a security engagement I have identified a security vulnerability in the Request library.
… (21 more lines in the stored log)
```

**Step 11** · `get_issue{"owner": "request", "repo": "request", "number": 3142}`
> 🗒 _The README directs users to this retirement discussion. Read the maintainer’s stated outcome and any migration guidance at the source._

```text
issue #3142: Request’s Past, Present and Future
state: open, opened 2019-03-30 by mikeal, 437 comments, labels: neverstale
body: Before I go into the details and reasoning I’ll get straight to the point. **The most valuable thing `request` can do for the JavaScript ecosystem is to go into maintenance mode and stop considering new features or major releases.**

Apologies in advance to the other committers on `request` that have been doing their best to improve it, but it’s for the best.

… (24 more lines in the stored log)
```

**Step 12** · `get_user{"login": "mikeal"}`  ← *following a lead beyond the repo*
> 🗒 _Mikeal is named as package author and is among the largest historical contributors. Profile the named maintainer behind the package’s stewardship._

```text
mikeal (User) — Mikeal Rogers
account created 2008-02-21, 509 public repos, 5,099 followers
location: San Francisco
bio: Hacker of a certain age.
```

**Step 13** · `get_user{"login": "simov"}`  ← *following a lead beyond the repo*
> 🗒 _Simov accounts for 26.9% of top-contributor commits, a material concentration. Identify whether this historical maintainer remains a plausible steward._

```text
simov (User) — simo
account created 2012-04-30, 131 public repos, 496 followers
company: Outofindex
location: EET/EEST
bio: (λ (λ (λ (λ (λ (⌐■_■))))))
```

**Step 14** · `get_user{"login": "nylen"}`  ← *following a lead beyond the repo*
> 🗒 _Nylen accounts for 17.0% of top-contributor commits. Profile this third major historical contributor to test whether maintenance was distributed or vanished._

```text
nylen (User) — James Nylen
account created 2010-03-20, 216 public repos, 230 followers
location: UTC-5 or -6 maybe
bio: I like to build things.
```

**Step 15** · `get_user_events{"login": "mikeal"}`  ← *following a lead beyond the repo*
> 🗒 _The repository is deprecated; Mikeal’s current public activity distinguishes a vanished account from an active person who simply no longer maintains this package._

```text
no public activity for mikeal in GitHub's recent-events window. NOTE: GitHub serves only ~90 days / 300 events of public activity — silence here does not prove long-term inactivity; use list_commits(author=...) for a durable timeline.
```

**Step 16** · `get_user_events{"login": "simov"}`  ← *following a lead beyond the repo*
> 🗒 _Simov is a major historical contributor. Recent public activity helps determine whether the project lacks a current steward rather than merely lacking commits._

```text
no public activity for simov in GitHub's recent-events window. NOTE: GitHub serves only ~90 days / 300 events of public activity — silence here does not prove long-term inactivity; use list_commits(author=...) for a durable timeline.
```

**Step 17** · `get_user_events{"login": "nylen"}`  ← *following a lead beyond the repo*
> 🗒 _Nylen is a major historical contributor. Recent public activity helps determine whether the project lacks a current steward rather than merely lacking commits._

```text
no public activity for nylen in GitHub's recent-events window. NOTE: GitHub serves only ~90 days / 300 events of public activity — silence here does not prove long-term inactivity; use list_commits(author=...) for a durable timeline.
```

**Step 18** · `list_commits{"owner": "request", "repo": "request", "since": "2019-01-01", "until": "2020-03-01", "author": "mikeal", "per_page": 30}`
> 🗒 _The deprecation window is decisive. Retrieve Mikeal’s commits around it to identify the named author of the retirement action and its exact scope._

```text
1 commits (since=2019-01-01, until=2020-03-01, author=mikeal, newest first):
- aded7e4f8e [2020-02-11] mikeal: doc: note full deprecation (#3267)
```

**Step 19** · `list_forks{"owner": "request", "repo": "request"}`  ← *following a lead beyond the repo*
> 🗒 _A deprecated project can still be viable only if its community moved to a maintained fork. Inspect the leading forks and their push dates._

```text
top 10 forks by stars (is the community maintaining one of these instead?):
- postmanlabs/postman-request: 155 stars, last push 2026-07-21
- linus/request: 77 stars, last push 2011-02-14
- cypress-io/request: 14 stars, last push 2026-08-26
- isaacs/request: 8 stars, last push 2014-09-08
- Flipboard/request: 6 stars, last push 2015-10-06
… (6 more lines in the stored log)
```

<sub>LLM call 4</sub>

**Step 20** · `render_verdict{"decision": "reject"}`
> 🗒 _The initially decisive abandonment finding has now been pursued to its named author, the unresolved security report, and the community-fork question. Mikeal authored the retirement action; the SSRF reporter records unanswered direct disclosure attempts; and the original package remains explicitly retired with no post-2020 merged maintenance._

```text
verdict v1 recorded: reject
```

### ↩︎ Re-tasked: “now check the biggest fork”

<sub>LLM call 5</sub>

**Step 21** · `get_repo{"owner": "postmanlabs", "repo": "postman-request"}`  ← *following a lead beyond the repo*
> 🗒 _The leading fork has 155 stars and a 2026 push, so it is the only plausible successor lead. Establish its ownership, archival state, and maintenance timestamps._

```text
postmanlabs/postman-request — Simplified HTTP request client.
stars 155, forks 49, open issues+PRs 3
created 2016-08-23, last push 2026-07-21, default branch master
license: Apache-2.0, language: JavaScript, size 3,022 KB
archived: False, disabled: False, fork: True (parent: request/request)
```

**Step 22** · `get_file{"owner": "postmanlabs", "repo": "postman-request", "path": "README.md"}`  ← *following a lead beyond the repo*
> 🗒 _A recent push does not prove a supported replacement. Read the fork’s own README for purpose, deprecation, and adoption guidance._

```text
README.md @ default branch (54,234 chars):

# Request - Simplified HTTP client

This is a fork of the excellent `request` module, which is used inside Postman Runtime. It contains a few bugfixes that are not fixed in `request`:

… (157 more lines in the stored log)
```

**Step 23** · `get_file{"owner": "postmanlabs", "repo": "postman-request", "path": "package.json"}`  ← *following a lead beyond the repo*
> 🗒 _The fork may publish under a different npm name and version. Its manifest determines whether consumers can practically adopt it and supports advisory lookup._

```text
package.json @ default branch (1,975 chars):
{
  "name": "postman-request",
  "description": "Simplified HTTP request client.",
  "keywords": [
    "http",
… (72 more lines in the stored log)
```

**Step 24** · `list_commits{"owner": "postmanlabs", "repo": "postman-request", "per_page": 30}`  ← *following a lead beyond the repo*
> 🗒 _The fork’s 2026 push could be mechanical. Inspect recent commits and authors to determine whether security-relevant maintenance actually landed._

```text
30 commits (no filters, newest first):
- 02741a5589 [2026-07-21] appurva21: 2.88.1-postman.49
- 286e0b28b0 [2026-07-21] MrRobotBaguette: APICLIENT-3136: security: strip Cookie on cross-origin redirect and use full-origin check (#113)
- bbc0e4e1f2 [2026-01-15] saecula: 2.88.1-postman.48
- 6354da7fc8 [2026-01-15] saecula: Merge pull request #111 from rm-maxport/update/qs-package
- 02963ca632 [2026-01-13] rm-maxport: chore: update qs package to latest version
… (26 more lines in the stored log)
```

**Step 25** · `list_pulls{"owner": "postmanlabs", "repo": "postman-request", "state": "all", "per_page": 20}`  ← *following a lead beyond the repo*
> 🗒 _Merged PR recency is stronger evidence of active governance than a push timestamp. Inspect the fork’s PR outcome._

```text
20 all PRs (most recently updated first):
- #114 [open] Update CI Node and Windows matrix (by appurva21)
- #113 [merged 2026-07-21] APICLIENT-3136: security: strip Cookie on cross-origin redirect and use full-ori (by MrRobotBaguette)
- #112 [open] Please deprecate beta versions that sort above stable releases due to semver ord (by Tsarter)
- #110 [open] BREAKING CHANGE : upgrade nodejs support till 24 and fix security vulns (by samarpanB)
- #111 [merged 2026-01-15] chore: update qs package to latest version (by rm-maxport)
… (16 more lines in the stored log)
```

**Step 26** · `list_issues{"owner": "postmanlabs", "repo": "postman-request", "state": "open", "sort": "updated", "per_page": 20}`  ← *following a lead beyond the repo*
> 🗒 _The original’s unresolved SSRF is decisive; inspect the fork’s live issues for its own vulnerability and responsiveness signal._

```text
no open issues found (3 pull requests excluded).
```

**Step 27** · `get_security_advisories{"owner": "postmanlabs", "repo": "postman-request"}`  ← *following a lead beyond the repo*
> 🗒 _Look for maintainer-published security records in the candidate successor, independent of its code lineage._

```text
no repository-published security advisories. NOTE: maintainers often never publish repo-level advisories even when CVEs exist — cross-check with osv_query using the package name from the manifest (e.g. package.json).
```

**Step 28** · `list_contributors{"owner": "postmanlabs", "repo": "postman-request"}`  ← *following a lead beyond the repo*
> 🗒 _If the fork is actively maintained, contributor concentration and named stewards matter. Establish whether it is a one-person veneer._

```text
top 10 of 30 listed contributors (share of the top-30 commit total — a proxy for bus factor):
- mikeal: 622 commits (29.6%)
- simov: 475 commits (22.6%)
- nylen: 300 commits (14.3%)
- codenirvana: 205 commits (9.7%)
- greenkeeperio-bot: 49 commits (2.3%)
… (5 more lines in the stored log)
```

<sub>LLM call 6</sub>

**Step 29** · `osv_query{"package": "postman-request", "ecosystem": "npm"}`  ← *following a lead beyond the repo*
> 🗒 _The fork is actively releasing under postman-request; query OSV for its published package identity before treating its security maintenance as sufficient._

```text
OSV: no known vulnerabilities recorded for npm package 'postman-request'.
```

**Step 30** · `get_commit{"owner": "postmanlabs", "repo": "postman-request", "sha": "286e0b28b0"}`  ← *following a lead beyond the repo*
> 🗒 _A 2026 commit claims to harden cross-origin redirects. Inspect its diff to determine whether it addresses the original SSRF/cross-origin security exposure or merely advertises security._

```text
commit 286e0b28b0 by MrRobotBaguette on 2026-07-21
message: APICLIENT-3136: security: strip Cookie on cross-origin redirect and use full-origin check (#113)
stats: 3 files changed, +362 -4

--- tests/test-redirect-cookie.js (+249 -0, added)
@@ -0,0 +1,249 @@
… (209 more lines in the stored log)
```

**Step 31** · `get_user{"login": "appurva21"}`  ← *following a lead beyond the repo*
> 🗒 _Appurva21 repeatedly authors releases and merges in the active fork. Profile the current release steward behind the candidate successor._

```text
appurva21 (User) — Appurva Murawat
account created 2017-01-08, 11 public repos, 28 followers
company: @postmanlabs
location: Bangalore
bio: Engineer @postmanlabs
```

**Step 32** · `get_user{"login": "MrRobotBaguette"}`  ← *following a lead beyond the repo*
> 🗒 _MrRobotBaguette authored the recent security-sensitive redirect change. Identify the named author behind that mitigation._

```text
MrRobotBaguette (User) — no display name
account created 2026-05-11, 0 public repos, 0 followers
```

**Step 33** · `get_user_events{"login": "appurva21"}`  ← *following a lead beyond the repo*
> 🗒 _The release steward’s current activity is a useful corroboration that the fork’s 2026 release cadence reflects an active maintainer._

```text
15 recent public events for appurva21, from 2026-08-07 to 2026-09-01: IssuesEvent×8, IssueCommentEvent×7
most recent: IssuesEvent on postmanlabs/postman-app-support at 2026-09-01
NOTE: GitHub serves only ~90 days / 300 events of public activity — silence here does not prove long-term inactivity; use list_commits(author=...) for a durable timeline.
```

**Step 34** · `get_user_events{"login": "MrRobotBaguette"}`  ← *following a lead beyond the repo*
> 🗒 _The security-change author’s recent activity helps distinguish an actively maintained organizational patch from an orphaned contribution._

```text
no public activity for MrRobotBaguette in GitHub's recent-events window. NOTE: GitHub serves only ~90 days / 300 events of public activity — silence here does not prove long-term inactivity; use list_commits(author=...) for a durable timeline.
```

<sub>LLM call 7</sub>

**Step 35** · `render_verdict{"decision": "reject"}`
> 🗒 _The largest fork is a genuinely active, separately published Postman-maintained derivative with a recent redirect credential-leak hardening patch and no OSV records. That is useful migration evidence, but it does not repair the decision on the requested dependency, request/request, whose explicit retirement and unfixed SSRF remain unchanged._

```text
SENIOR REVIEW: verdict (reject) handed back for a second look after 3 call(s) — anomalies must be pursued or explicitly closed before concluding
```

<sub>LLM call 8</sub>

**Step 36** · `get_commit{"owner": "request", "repo": "request", "sha": "aded7e4f8e"}`
> 🗒 _The original deprecation author is named, but the exact diff has not been read. Inspect it to close the named-author outcome on the retirement action._

```text
commit aded7e4f8e by mikeal on 2020-02-11
message: doc: note full deprecation (#3267)
stats: 1 files changed, +6 -0

--- README.md (+6 -0, modified)
@@ -1,3 +1,9 @@
… (9 more lines in the stored log)
```

**Step 37** · `get_commit{"owner": "postmanlabs", "repo": "postman-request", "sha": "02741a5589"}`  ← *following a lead beyond the repo*
> 🗒 _The candidate fork’s July 2026 version bump may be the release commit for its security patch. Inspect its diff to establish whether the security change was actually versioned._

```text
commit 02741a5589 by appurva21 on 2026-07-21
message: 2.88.1-postman.49
stats: 1 files changed, +1 -1

--- package.json (+1 -1, modified)
@@ -7,7 +7,7 @@
… (8 more lines in the stored log)
```

**Step 38** · `list_commits{"owner": "postmanlabs", "repo": "postman-request", "since": "2026-07-20", "until": "2026-07-22", "author": "appurva21", "per_page": 30}`  ← *following a lead beyond the repo*
> 🗒 _Appurva21 is the organizational release steward; inspect their commits around the latest release to link named stewardship to the published version._

```text
1 commits (since=2026-07-20, until=2026-07-22, author=appurva21, newest first):
- 02741a5589 [2026-07-21] appurva21: 2.88.1-postman.49
```

**Step 39** · `list_commits{"owner": "postmanlabs", "repo": "postman-request", "since": "2026-07-20", "until": "2026-07-22", "author": "MrRobotBaguette", "per_page": 30}`  ← *following a lead beyond the repo*
> 🗒 _MrRobotBaguette authored the redirect hardening patch. Retrieve their fork timeline around the patch to close the named-author outcome._

```text
1 commits (since=2026-07-20, until=2026-07-22, author=MrRobotBaguette, newest first):
- 286e0b28b0 [2026-07-21] MrRobotBaguette: APICLIENT-3136: security: strip Cookie on cross-origin redirect and use full-origin check (#113)
```

**Step 40** · `get_user{"login": "SzymonDrosdzol"}`  ← *following a lead beyond the repo*
> 🗒 _The original SSRF report is an unanswered-security-report anomaly. Identify its named reporter so the disclosure outcome is attributed rather than anonymous._

```text
SzymonDrosdzol (User) — no display name
account created 2021-05-24, 3 public repos, 7 followers
company: Doyensec
```

<sub>LLM call 9</sub>

**Step 41** · `render_verdict{"decision": "reject"}`
> 🗒 _The review-requested anomalies have now been closed: no malicious-code record was returned; the original retirement was authored by Mikeal and its full-deprecation diff was inspected; the unanswered SSRF disclosure is attributed to SzymonDrosdzol of Doyensec; and the fork’s current security patch, named author, and release bump were inspected. The original package’s decisive abandonment and unfixed SSRF findings remain intact._

```text
verdict v2 recorded: reject
```

## Budget ledger

- Initial budget: 30 LLM calls · used: 9 · remaining: 21
- 41 investigation steps in 9 LLM calls (a call that batches N tool calls produces N steps but costs 1)

---
_Generated 2026-09-02 07:58 UTC · every evidence item cites an investigation step; anything that couldn't be verified is labeled as such._
