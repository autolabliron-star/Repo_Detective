# The Case of expressjs/express

## Verdict: ✅ ADOPT · confidence: high

> Adopt express. No malicious-code or hidden-functionality record was returned by the package OSV or repository-advisory checks; the repository’s documented rejected advisory explicitly says there was no actual vulnerability. The historical dominant author is TJ (whose newest listed Express commit is 2014), while current work is contributed by multiple named accounts and includes a concrete security dependency fix. The sole unanswered security report alleged qs 6.15.2 vulnerabilities, but OSV returns none for that exact version. No leading fork shows evidence of a community maintenance migration. Repository/package identity is consistent: the manifest names npm package express and repository expressjs/express.

**Evidence** (every item mechanically checked against the log):
- ✔ The repository is active, non-archived, and not a fork.  
  _step 1:_ “last push 2026-09-01, default branch master
license: MIT, language: JavaScript”
- ✔ The package manifest identifies npm package express and its canonical repository.  
  _step 2:_ “"name": "express",
 "description": "Fast, unopinionated, minimalist web framework",
 "version": "5.2.1"”
- ✔ OSV reports no known vulnerabilities for the current 5.2.1 package version.  
  _step 15:_ “OSV: no known vulnerabilities recorded for npm package 'express' @ 5.2.1.”
- ✔ OSV reports no known vulnerabilities for the exact qs 6.15.2 version alleged in the unanswered issue.  
  _step 18:_ “OSV: no known vulnerabilities recorded for npm package 'qs' @ 6.15.2.”
- ✔ The repository changelog states that the rejected advisory had no actual security vulnerability.  
  _step 22:_ “There is no actual security vulnerability associated with this behavior (CVE-2024-51999 has been rejected).”
- ✔ Recent history contains a named security remediation by Mayvis.  
  _step 10:_ “commit 8ba0c07fdc by Mayvis on 2026-08-22
message: deps: bump body-parser to ^2.3.0 to fix CVE-2026-12590”
- ✔ The historically dominant contributor TJ’s newest listed Express commit is from 2014, not current maintenance.  
  _step 11:_ “10 commits (author=tj, newest first):
- 6b05f60bad [2014-02-19] tj: update node-fresh”
- ✔ Recent commits show multiple human contributors alongside automated updates.  
  _step 21:_ “- ae6dd37680 [2026-07-12] Cherry: feat: allow conditional revalidation for QUERY requests (#7366)”

**Could not be verified:**
- GitHub/npm publisher permissions and release provenance were not available through the provided tools.
- GitHub recent-events windows showed no public activity for TJ or Douglas Wilson, but the tool explicitly notes that this does not prove long-term inactivity.

## The Tip-off (intake — plain code, no LLM)

- Fast, unopinionated, minimalist web framework for node.
- ⭐ 69,417 stars · 24,909 forks · 236 open issues+PRs
- Language: JavaScript · License: MIT
- Created 2009-06-26 · last push 2026-09-01
- Releases: latest release v4.22.2 on 2026-05-11
- Top contributors: tj (68.8%), dougwilson (21.8%), jonathanong (1.5%), defunctzombie (1.2%), dependabot[bot] (0.9%)

## The Investigation

_One LLM call can batch several tool calls, so step numbers run past the call count; each call is marked below._

<sub>LLM call 1</sub>

**Step 1** · `get_repo{"owner": "expressjs", "repo": "express"}`
> 🗒 _Intake shows a live, non-archived repository pushed yesterday. Confirm the repository’s current identity and maintenance metadata from the investigation tools._

```text
expressjs/express — Fast, unopinionated, minimalist web framework for node.
stars 69,417, forks 24,909, open issues+PRs 236
created 2009-06-26, last push 2026-09-01, default branch master
license: MIT, language: JavaScript, size 9,861 KB
archived: False, disabled: False, fork: False
homepage: https://expressjs.com
… (1 more lines in the stored log)
```

**Step 2** · `get_file{"owner": "expressjs", "repo": "express", "path": "package.json"}`
> 🗒 _The package manifest establishes the published npm identity and scripts before vulnerability records are trusted._

```text
package.json @ default branch (2,559 chars):
{
 "name": "express",
 "description": "Fast, unopinionated, minimalist web framework",
 "version": "5.2.1",
 "author": "TJ Holowaychuk <tj@vision-media.ca>",
… (94 more lines in the stored log)
```

**Step 3** · `osv_query{"package": "express", "ecosystem": "npm"}`  ← *following a lead beyond the repo*
> 🗒 _A popular active repository can still have shipped vulnerable or malicious releases; OSV is the first severity screen for the published package._

```text
OSV: 5 known vulnerabilities for npm package 'express':
- GHSA-cm5g-3pgc-8rg4 (CVE-2024-10491) [CVSS3 CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:C/C:L/I:N/A:N] published 2024-10-29
  Express ressource injection
  introduced 0, fixed 4.0.0-rc1
- GHSA-gpvr-g6gh-9mc2 (CVE-2014-6393) [CVSS3 CVSS:3.0/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N] published 2018-10-23
  No Charset in Content-Type Header in express
… (10 more lines in the stored log)
```

**Step 4** · `get_security_advisories{"owner": "expressjs", "repo": "express"}`
> 🗒 _Repository advisories may disclose incidents not obvious from activity metrics, so compare them with the package-level OSV record._

```text
3 repository security advisories:
- GHSA-pj86-cfqh-vqx6 / CVE-2024-51999 [low] published 2025-12-01: REJECTED (not a vulnerability): improperly controlled modification of query properties in express
- GHSA-qw6h-vgh9-j6wx / CVE-2024-43796 [medium] published 2024-09-10: express vulnerable to XSS via response.redirect()
- GHSA-rv95-896h-c2vc / CVE-2024-29041 [medium] published 2024-03-25: Express.js Open Redirect in malformed URLs
```

**Step 5** · `list_commits{"owner": "expressjs", "repo": "express", "per_page": 20}`
> 🗒 _The intake says the repository was pushed yesterday. Read the recent commit stream to distinguish real maintenance from incidental churn._

```text
20 commits (no filters, newest first):
- 023767fe98 [2026-08-22] dependabot[bot]: build(deps): bump github/codeql-action/upload-sarif (#7400)
- 2574a53bbc [2026-08-22] dependabot[bot]: build(deps): bump coverallsapp/github-action from 2.3.7 to 2.3.8 (#7399)
- 91d333b4cf [2026-08-22] spellsaif: docs(res.location): clean up deprecated back string references (#7406)
- 28f732e98f [2026-08-22] dependabot[bot]: build(deps): bump actions/checkout from 7.0.0 to 7.0.1 (#7403)
- 8ba0c07fdc [2026-08-22] Mayvis: deps: bump body-parser to ^2.3.0 to fix CVE-2026-12590 (#7390)
… (16 more lines in the stored log)
```

**Step 6** · `list_pulls{"owner": "expressjs", "repo": "express", "state": "closed", "per_page": 20}`
> 🗒 _Merged pull requests reveal whether review and integration are current, rather than merely a branch timestamp._

```text
20 closed PRs (most recently updated first):
- #7451 [closed] fix: accept a comma-delimited list in req.acceptsCharsets (by marceli1404)
- #7402 [closed] build(deps): bump github/codeql-action/analyze from 4.36.0 to 4.37.3 (by dependabot[bot])
- #7401 [closed] build(deps): bump github/codeql-action/init from 4.36.0 to 4.37.3 (by dependabot[bot])
- #7435 [closed] feat(app): warn when HEAD route is declared after GET route on the same path (by santusht06)
- #7438 [closed] fix(res): support raw ArrayBuffer in res.send() (by vaibhavmashal)
… (16 more lines in the stored log)
```

**Step 7** · `list_issues{"owner": "expressjs", "repo": "express", "state": "open", "sort": "updated", "per_page": 20}`
> 🗒 _Open issue responsiveness is the practical maintenance signal; inspect the current queue for unanswered security or abandonment warnings._

```text
7 open issues, sorted by updated (23 PRs excluded from the issues feed):
- #2414 [open] (21 comments, opened 2014-10-26) route() should handle 405 Method not allowed
- #6353 [open] (10 comments, opened 2025-02-20) Support diagnostic channels
- #7439 [open] (0 comments, opened 2026-09-01) Express 4.22.2 has qs vulnerable dependency
- #7427 [open] (1 comments, opened 2026-08-25) router.use() silently accepts express() sub-apps  without prototype restoration
- #7350 [open] (6 comments, opened 2026-07-01) res.render()/app.render() throws opaque TypeError for a view name ending in "."
… (3 more lines in the stored log)
```

**Step 8** · `list_releases{"owner": "expressjs", "repo": "express"}`
> 🗒 _Recent releases connect repository activity to consumable package maintenance and provide a release cadence check._

```text
10 most recent GitHub releases:
- v4.22.2 "v4.22.2" published 2026-05-11
- v5.2.1 "v5.2.1" published 2025-12-01
- v5.2.0 "v5.2.0" published 2025-12-01
- v4.22.1 "v4.22.1" published 2025-12-01
- 4.22.0 "4.22.0" published 2025-12-01
… (5 more lines in the stored log)
```

<sub>LLM call 2</sub>

**Step 9** · `get_issue{"owner": "expressjs", "repo": "express", "number": 7439}`
> 🗒 _The only unanswered current issue alleges a vulnerable shipped dependency. Read the report before treating it as a verified exposure._

```text
issue #7439: Express 4.22.2 has qs vulnerable dependency
state: open, opened 2026-09-01 by samarth444, 0 comments, labels: 4.x, deps
body: <!-- The process for bug fixing is:

- We will first assess if the behavior is different from what should occur
- Confirm the bug is reproducible
… (34 more lines in the stored log)
```

**Step 10** · `get_commit{"owner": "expressjs", "repo": "express", "sha": "8ba0c07fdc"}`
> 🗒 _Recent history says body-parser was bumped to fix CVE-2026-12590. Inspect the exact change to establish whether dependency remediation reached the manifest._

```text
commit 8ba0c07fdc by Mayvis on 2026-08-22
message: deps: bump body-parser to ^2.3.0 to fix CVE-2026-12590 (#7390)

body-parser < 2.3.0 silently disables request body size enforcement
when given an invalid `limit` option value (bytes.parse() returns null),
allowing a denial of service via arbitrarily large payloads
… (27 more lines in the stored log)
```

**Step 11** · `list_commits{"owner": "expressjs", "repo": "express", "author": "tj", "per_page": 10}`
> 🗒 _TJ owns 68.8% of the top-30 commit total in intake. Determine whether that historical concentration represents current control or an inactive founder._

```text
10 commits (author=tj, newest first):
- 6b05f60bad [2014-02-19] tj: update node-fresh
- a5f7dcee04 [2014-01-29] tj: update node-fresh
- 827dfed7c2 [2014-01-05] tj: Merge pull request #1890 from oliversalzburg/patch-1
- dc5932d177 [2013-12-23] tj: Merge pull request #1877 from reqshark/master
- 3baca251f0 [2013-12-22] tj: use 8 threads for benchmarks
… (6 more lines in the stored log)
```

**Step 12** · `list_commits{"owner": "expressjs", "repo": "express", "author": "dougwilson", "per_page": 10}`
> 🗒 _The second historical contributor holds 21.8%; inspect their recent repository activity to assess whether maintenance is concentrated in a living maintainer._

```text
10 commits (author=dougwilson, newest first):
- a22920707b [2023-11-02] dougwilson: build: actions/checkout@v4
- 02d1c3916e [2023-08-24] dougwilson: build: Node.js@19.9
- 8d8bfaac7b [2023-08-23] dougwilson: build: Node.js@18.17
- 13df1de857 [2023-08-23] dougwilson: build: eslint@8.47.0
- 24e4a2570d [2023-04-07] dougwilson: build: Node.js@16.20
… (6 more lines in the stored log)
```

**Step 13** · `get_user{"login": "tj"}`  ← *following a lead beyond the repo*
> 🗒 _The dominant historical author warrants identity and current-account context, especially if their repository activity has faded._

```text
tj (User) — TJ
account created 2008-09-18, 296 public repos, 52,902 followers
company: Apex
```

**Step 14** · `get_user{"login": "dougwilson"}`  ← *following a lead beyond the repo*
> 🗒 _The second dominant contributor is the natural continuity lead; profile the account alongside their commit history._

```text
dougwilson (User) — Douglas Wilson
account created 2009-03-26, 31 public repos, 3,734 followers
bio: ¯\_(ツ)_/¯
```

**Step 15** · `osv_query{"package": "express", "ecosystem": "npm", "version": "5.2.1"}`  ← *following a lead beyond the repo*
> 🗒 _The default-branch manifest declares express 5.2.1. Query that exact version to separate historical advisories from current package exposure._

```text
OSV: no known vulnerabilities recorded for npm package 'express' @ 5.2.1.
```

**Step 16** · `osv_query{"package": "express", "ecosystem": "npm", "version": "4.22.2"}`  ← *following a lead beyond the repo*
> 🗒 _The latest 4.x release remains a likely consumer choice. Query its exact version because the open issue specifically names 4.22.2._

```text
OSV: no known vulnerabilities recorded for npm package 'express' @ 4.22.2.
```

<sub>LLM call 3</sub>

**Step 17** · `render_verdict{"decision": "adopt"}`
> 🗒 _The current package versions have no OSV-recorded vulnerabilities, the sole fresh dependency allegation is unreviewed, and recent commits show active remediation. The historical founder concentration is real but no longer represents current commit activity; it is not a decisive supply-chain anomaly on this evidence._

```text
SENIOR REVIEW: verdict (adopt) handed back for a second look after 3 call(s) — anomalies must be pursued or explicitly closed before concluding
```

<sub>LLM call 4</sub>

**Step 18** · `osv_query{"package": "qs", "ecosystem": "npm", "version": "6.15.2"}`  ← *following a lead beyond the repo*
> 🗒 _Issue #7439 names qs 6.15.2 and two CVEs. Query the exact transitive version rather than letting an unreviewed report decide the case._

```text
OSV: no known vulnerabilities recorded for npm package 'qs' @ 6.15.2.
```

**Step 19** · `get_user_events{"login": "tj"}`  ← *following a lead beyond the repo*
> 🗒 _TJ’s newest Express commit is from 2014 despite historical dominance. Their current public activity may clarify whether this is a vanished maintainer or merely a founder no longer committing here._

```text
no public activity for tj in GitHub's recent-events window. NOTE: GitHub serves only ~90 days / 300 events of public activity — silence here does not prove long-term inactivity; use list_commits(author=...) for a durable timeline.
```

**Step 20** · `get_user_events{"login": "dougwilson"}`  ← *following a lead beyond the repo*
> 🗒 _Douglas Wilson’s newest listed Express commit is 2023. Check current public activity to assess whether the historical core has vanished from GitHub entirely._

```text
no public activity for dougwilson in GitHub's recent-events window. NOTE: GitHub serves only ~90 days / 300 events of public activity — silence here does not prove long-term inactivity; use list_commits(author=...) for a durable timeline.
```

**Step 21** · `list_commits{"owner": "expressjs", "repo": "express", "since": "2025-12-01", "per_page": 30}`
> 🗒 _Recent commits came from varied authors, but the named people who integrate releases remain unclear. Expand the post-5.2.1 timeline to identify current human maintainers and release-related changes._

```text
30 commits (since=2025-12-01, newest first):
- 023767fe98 [2026-08-22] dependabot[bot]: build(deps): bump github/codeql-action/upload-sarif (#7400)
- 2574a53bbc [2026-08-22] dependabot[bot]: build(deps): bump coverallsapp/github-action from 2.3.7 to 2.3.8 (#7399)
- 91d333b4cf [2026-08-22] spellsaif: docs(res.location): clean up deprecated back string references (#7406)
- 28f732e98f [2026-08-22] dependabot[bot]: build(deps): bump actions/checkout from 7.0.0 to 7.0.1 (#7403)
- 8ba0c07fdc [2026-08-22] Mayvis: deps: bump body-parser to ^2.3.0 to fix CVE-2026-12590 (#7390)
… (26 more lines in the stored log)
```

**Step 22** · `get_file{"owner": "expressjs", "repo": "express", "path": "History.md"}`
> 🗒 _The repository’s own changelog can connect current package versions to security fixes and reveal whether any malicious or hidden-functionality incident is documented._

```text
History.md @ default branch (127,746 chars):
# Unreleased Changes

## 🐞 Bug fixes

- Fixed HTTP header conflict between Content-Length and Transfer-Encoding in res.send - by [@YuryShkoda](https://github.com/YuryShkoda) in [#4893](https://github.com/expressjs/express/pull/4893)
… (88 more lines in the stored log)
```

**Step 23** · `list_forks{"owner": "expressjs", "repo": "express"}`  ← *following a lead beyond the repo*
> 🗒 _A long-lived project with old core contributors could have lost its community to a fork. Inspect the leading forks for evidence of a maintenance migration._

```text
top 10 forks by stars (is the community maintaining one of these instead?):
- Mihaeth/express: 18 stars, last push 2025-02-14
- hamidreza01/express: 16 stars, last push 2022-06-28
- Anilnayak126/express: 9 stars, last push 2024-07-28
- jayDevCodes/express: 9 stars, last push 2026-02-14
- brajrj/express: 8 stars, last push 2024-10-06
… (6 more lines in the stored log)
```

<sub>LLM call 5</sub>

**Step 24** · `render_verdict{"decision": "adopt"}`
> 🗒 _The senior review required the raised anomalies be closed. OSV clears the exact qs version, no malicious-code record appeared in either advisory source, the historical founder is named and inactive in this repository while recent work is multi-author, and forks show no maintenance migration. The evidence now supports a compact final verdict._

```text
verdict v1 recorded: adopt
```

## Budget ledger

- Initial budget: 30 LLM calls · used: 5 · remaining: 25
- 24 investigation steps in 5 LLM calls (a call that batches N tool calls produces N steps but costs 1)

---
_Generated 2026-09-02 07:57 UTC · every evidence item cites an investigation step; anything that couldn't be verified is labeled as such._
