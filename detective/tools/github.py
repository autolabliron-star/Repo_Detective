"""GitHub tool implementations.

Every tool returns (observation: str, api_requests: int). Observations are
compact, human-readable text — never raw API JSON — with hard caps so 30 LLM
calls fit comfortably in context. Trimmers are designed so LEADS ARE VISIBLE:
contributor share %, unanswered-issue summaries, fork freshness. Truncations
are always marked so the agent knows it can drill deeper.

Errors come back as observations too ("ERROR (empty_repository): ...") — the
agent reasons about them; nothing raises into the loop.
"""

from __future__ import annotations

from ..github_client import GitHubClient

MAX_COMMITS = 30
MAX_ISSUES = 20
MAX_FILE_CHARS = 6000
MAX_PATCH_FILES = 15
MAX_PATCH_LINES = 80


def _err(res: dict) -> tuple[str, int]:
    extra = f" — resets {res['resets_at']}" if res.get("resets_at") else ""
    return f"ERROR ({res['error']}): {res['message']}{extra}", res.get("api_requests", 1)


def _d(iso: str | None) -> str:
    return (iso or "?")[:10]


def _n(x) -> str:
    return f"{x:,}" if isinstance(x, int) else "?"


# --------------------------------------------------------------------- #


def get_repo(gh: GitHubClient, a: dict) -> tuple[str, int]:
    res = gh.get(f"/repos/{a['owner']}/{a['repo']}")
    if not res["ok"]:
        return _err(res)
    d = res["data"]
    lines = [
        f"{d['full_name']} — {d.get('description') or 'no description'}",
        f"stars {_n(d.get('stargazers_count'))}, forks {_n(d.get('forks_count'))}, "
        f"open issues+PRs {_n(d.get('open_issues_count'))}",
        f"created {_d(d.get('created_at'))}, last push {_d(d.get('pushed_at'))}, "
        f"default branch {d.get('default_branch')}",
        f"license: {(d.get('license') or {}).get('spdx_id') or 'none'}, "
        f"language: {d.get('language')}, size {_n(d.get('size'))} KB",
        f"archived: {d.get('archived')}, disabled: {d.get('disabled')}, fork: {d.get('fork')}"
        + (f" (parent: {d['parent']['full_name']})" if d.get("parent") else ""),
    ]
    if d.get("homepage"):
        lines.append(f"homepage: {d['homepage']}")
    if d.get("topics"):
        lines.append("topics: " + ", ".join(d["topics"][:10]))
    return "\n".join(lines), 1


def list_commits(gh: GitHubClient, a: dict) -> tuple[str, int]:
    params: dict = {"per_page": min(int(a.get("per_page", MAX_COMMITS)), MAX_COMMITS)}
    for key in ("since", "until", "author"):
        if a.get(key):
            params[key] = a[key]
    res = gh.get(f"/repos/{a['owner']}/{a['repo']}/commits", params=params)
    if not res["ok"]:
        return _err(res)
    commits = res["data"]
    filt = ", ".join(f"{k}={v}" for k, v in params.items() if k != "per_page") or "no filters"
    if not commits:
        return f"0 commits returned ({filt}) — nothing in this window/filter.", 1
    lines = [f"{len(commits)} commits ({filt}, newest first):"]
    for c in commits:
        login = (c.get("author") or {}).get("login") or (c.get("commit", {}).get("author") or {}).get("name", "?")
        msg = (c.get("commit", {}).get("message") or "").splitlines()[0][:100]
        date = _d((c.get("commit", {}).get("author") or {}).get("date"))
        lines.append(f"- {c.get('sha', '')[:10]} [{date}] {login}: {msg}")
    if len(commits) == params["per_page"]:
        lines.append(f"(showing the {params['per_page']} most recent — there may be more; narrow with since/until/author)")
    return "\n".join(lines), 1


def get_commit(gh: GitHubClient, a: dict) -> tuple[str, int]:
    res = gh.get(f"/repos/{a['owner']}/{a['repo']}/commits/{a['sha']}")
    if not res["ok"]:
        return _err(res)
    d = res["data"]
    stats = d.get("stats", {})
    author = (d.get("author") or {}).get("login") or (d.get("commit", {}).get("author") or {}).get("name", "?")
    lines = [
        f"commit {d.get('sha', '')[:10]} by {author} on {_d((d.get('commit', {}).get('author') or {}).get('date'))}",
        f"message: {(d.get('commit', {}).get('message') or '')[:400]}",
        f"stats: {len(d.get('files', []))} files changed, +{stats.get('additions', 0)} -{stats.get('deletions', 0)}",
    ]
    files = sorted(d.get("files", []), key=lambda f: f.get("additions", 0), reverse=True)
    for f in files[:MAX_PATCH_FILES]:
        lines.append(f"\n--- {f.get('filename')} (+{f.get('additions', 0)} -{f.get('deletions', 0)}, {f.get('status')})")
        patch = f.get("patch")
        if patch:
            plines = patch.splitlines()
            lines.extend(plines[:MAX_PATCH_LINES])
            if len(plines) > MAX_PATCH_LINES:
                lines.append(f"...[patch truncated, {len(plines) - MAX_PATCH_LINES} more lines]")
        else:
            lines.append("(no text diff available — binary or too large)")
    if len(files) > MAX_PATCH_FILES:
        lines.append(f"\n...[{len(files) - MAX_PATCH_FILES} more files not shown]")
    return "\n".join(lines), 1


def list_contributors(gh: GitHubClient, a: dict) -> tuple[str, int]:
    res = gh.get(f"/repos/{a['owner']}/{a['repo']}/contributors", params={"per_page": 30})
    if not res["ok"]:
        return _err(res)
    people = res["data"]
    if not people:
        return "no contributors listed — the repository may be empty.", 1
    total = sum(c.get("contributions", 0) for c in people) or 1
    lines = [f"top {min(10, len(people))} of {len(people)} listed contributors "
             f"(share of the top-{len(people)} commit total — a proxy for bus factor):"]
    for c in people[:10]:
        login = c.get("login", "?")
        n = c.get("contributions", 0)
        bot = " (bot)" if login.endswith("[bot]") else ""
        lines.append(f"- {login}{bot}: {n:,} commits ({100.0 * n / total:.1f}%)")
    return "\n".join(lines), 1


def list_issues(gh: GitHubClient, a: dict) -> tuple[str, int]:
    params = {
        "state": a.get("state", "open"),
        "sort": a.get("sort", "created"),
        "direction": "desc",
        "per_page": min(int(a.get("per_page", MAX_ISSUES)) + 10, 30),  # over-fetch: PRs get filtered out
    }
    res = gh.get(f"/repos/{a['owner']}/{a['repo']}/issues", params=params)
    if not res["ok"]:
        return _err(res)
    raw = res["data"]
    issues = [i for i in raw if "pull_request" not in i][:MAX_ISSUES]
    prs_excluded = len(raw) - len([i for i in raw if "pull_request" not in i])
    if not issues:
        return f"no {params['state']} issues found ({prs_excluded} pull requests excluded).", 1
    lines = [f"{len(issues)} {params['state']} issues, sorted by {params['sort']} "
             f"({prs_excluded} PRs excluded from the issues feed):"]
    unanswered = 0
    oldest_unanswered = None
    for i in issues:
        c = i.get("comments", 0)
        if c == 0 and not i.get("assignee"):
            unanswered += 1
            oldest_unanswered = i  # list is desc; last hit is the oldest
        assigned = ", assigned" if i.get("assignee") else ""
        lines.append(f"- #{i['number']} [{i['state']}] ({c} comments, opened {_d(i.get('created_at'))}{assigned}) "
                     f"{(i.get('title') or '')[:90]}")
    summary = f"summary: {unanswered} of {len(issues)} listed issues have 0 comments and no assignee"
    if oldest_unanswered is not None:
        summary += f"; oldest such issue: #{oldest_unanswered['number']} from {_d(oldest_unanswered.get('created_at'))}"
    lines.append(summary)
    return "\n".join(lines), 1


def get_issue(gh: GitHubClient, a: dict) -> tuple[str, int]:
    o, r, n = a["owner"], a["repo"], a["number"]
    res = gh.get(f"/repos/{o}/{r}/issues/{n}")
    if not res["ok"]:
        return _err(res)
    d = res["data"]
    kind = "pull request" if "pull_request" in d else "issue"
    labels = ", ".join(l.get("name", "") for l in d.get("labels", [])) or "none"
    lines = [
        f"{kind} #{n}: {d.get('title')}",
        f"state: {d.get('state')}{' (closed ' + _d(d.get('closed_at')) + ')' if d.get('closed_at') else ''}, "
        f"opened {_d(d.get('created_at'))} by {(d.get('user') or {}).get('login', '?')}, "
        f"{d.get('comments', 0)} comments, labels: {labels}",
        f"body: {(d.get('body') or '(empty)')[:1500]}",
    ]
    api = 1
    if d.get("comments", 0) > 0:
        cres = gh.get(f"/repos/{o}/{r}/issues/{n}/comments", params={"per_page": 5})
        api += 1
        if cres["ok"]:
            for c in cres["data"]:
                lines.append(f"--- comment by {(c.get('user') or {}).get('login', '?')} [{_d(c.get('created_at'))}]: "
                             f"{(c.get('body') or '')[:400]}")
            if d.get("comments", 0) > 5:
                lines.append(f"...[{d['comments'] - 5} more comments not shown]")
    return "\n".join(lines), api


def list_pulls(gh: GitHubClient, a: dict) -> tuple[str, int]:
    params = {
        "state": a.get("state", "closed"),
        "sort": "updated",
        "direction": "desc",
        "per_page": min(int(a.get("per_page", MAX_ISSUES)), MAX_ISSUES),
    }
    res = gh.get(f"/repos/{a['owner']}/{a['repo']}/pulls", params=params)
    if not res["ok"]:
        return _err(res)
    pulls = res["data"]
    if not pulls:
        return f"no {params['state']} pull requests found.", 1
    lines = [f"{len(pulls)} {params['state']} PRs (most recently updated first):"]
    merged = 0
    latest_merge = None
    for p in pulls:
        m = p.get("merged_at")
        if m:
            merged += 1
            latest_merge = max(latest_merge or m, m)
        status = f"merged {_d(m)}" if m else p.get("state", "?")
        lines.append(f"- #{p['number']} [{status}] {(p.get('title') or '')[:80]} "
                     f"(by {(p.get('user') or {}).get('login', '?')})")
    if params["state"] != "open":
        lines.append(f"summary: {merged} of {len(pulls)} listed PRs were merged"
                     + (f"; most recent merge {_d(latest_merge)}" if latest_merge else "; none merged"))
    return "\n".join(lines), 1


def list_releases(gh: GitHubClient, a: dict) -> tuple[str, int]:
    o, r = a["owner"], a["repo"]
    res = gh.get(f"/repos/{o}/{r}/releases", params={"per_page": 10})
    if not res["ok"]:
        return _err(res)
    releases = res["data"]
    if releases:
        lines = [f"{len(releases)} most recent GitHub releases:"]
        for rel in releases:
            pre = " (pre-release)" if rel.get("prerelease") else ""
            lines.append(f"- {rel.get('tag_name')} \"{(rel.get('name') or '')[:60]}\" "
                         f"published {_d(rel.get('published_at'))}{pre}")
        return "\n".join(lines), 1
    tags = gh.get(f"/repos/{o}/{r}/tags", params={"per_page": 10})
    if tags["ok"] and tags["data"]:
        names = ", ".join(t.get("name", "?") for t in tags["data"])
        return (f"no GitHub releases. {len(tags['data'])} most recent tags (names only — tags carry no dates; "
                f"use list_commits for timing): {names}"), 2
    return "no GitHub releases and no tags — nothing has ever been versioned here.", 2


def get_file(gh: GitHubClient, a: dict) -> tuple[str, int]:
    params = {"ref": a["ref"]} if a.get("ref") else None
    res = gh.get(f"/repos/{a['owner']}/{a['repo']}/contents/{a['path']}",
                 params=params, accept="application/vnd.github.raw+json")
    if not res["ok"]:
        return _err(res)
    text = res["data"] if isinstance(res["data"], str) else str(res["data"])
    header = f"{a['path']} @ {a.get('ref') or 'default branch'} ({len(text):,} chars):"
    if len(text) > MAX_FILE_CHARS:
        return f"{header}\n{text[:MAX_FILE_CHARS]}\n...[truncated — {len(text) - MAX_FILE_CHARS:,} more chars]", 1
    return f"{header}\n{text}", 1


def list_forks(gh: GitHubClient, a: dict) -> tuple[str, int]:
    res = gh.get(f"/repos/{a['owner']}/{a['repo']}/forks",
                 params={"sort": "stargazers", "per_page": 10})
    if not res["ok"]:
        return _err(res)
    forks = res["data"]
    if not forks:
        return "no forks found.", 1
    lines = [f"top {len(forks)} forks by stars (is the community maintaining one of these instead?):"]
    for f in forks:
        lines.append(f"- {f.get('full_name')}: {f.get('stargazers_count', 0):,} stars, "
                     f"last push {_d(f.get('pushed_at'))}")
    lines.append("(point any tool at a fork via its owner/repo to investigate it)")
    return "\n".join(lines), 1


def get_security_advisories(gh: GitHubClient, a: dict) -> tuple[str, int]:
    res = gh.get(f"/repos/{a['owner']}/{a['repo']}/security-advisories")
    if not res["ok"]:
        return _err(res)
    advisories = res["data"]
    if not advisories:
        return ("no repository-published security advisories. NOTE: maintainers often never publish repo-level "
                "advisories even when CVEs exist — cross-check with osv_query using the package name from the "
                "manifest (e.g. package.json)."), 1
    lines = [f"{len(advisories)} repository security advisories:"]
    for adv in advisories[:10]:
        lines.append(f"- {adv.get('ghsa_id')} / {adv.get('cve_id') or 'no CVE'} [{adv.get('severity')}] "
                     f"published {_d(adv.get('published_at'))}: {(adv.get('summary') or '')[:120]}")
    return "\n".join(lines), 1


def get_user(gh: GitHubClient, a: dict) -> tuple[str, int]:
    res = gh.get(f"/users/{a['login']}")
    if not res["ok"]:
        return _err(res)
    d = res["data"]
    lines = [
        f"{d.get('login')} ({d.get('type')}) — {d.get('name') or 'no display name'}",
        f"account created {_d(d.get('created_at'))}, {d.get('public_repos', 0)} public repos, "
        f"{d.get('followers', 0):,} followers",
    ]
    if d.get("company"):
        lines.append(f"company: {d['company']}")
    if d.get("location"):
        lines.append(f"location: {d['location']}")
    if d.get("bio"):
        lines.append(f"bio: {d['bio'][:200]}")
    return "\n".join(lines), 1


def get_user_events(gh: GitHubClient, a: dict) -> tuple[str, int]:
    res = gh.get(f"/users/{a['login']}/events/public", params={"per_page": 30})
    if not res["ok"]:
        return _err(res)
    events = res["data"]
    note = ("NOTE: GitHub serves only ~90 days / 300 events of public activity — silence here does not prove "
            "long-term inactivity; use list_commits(author=...) for a durable timeline.")
    if not events:
        return f"no public activity for {a['login']} in GitHub's recent-events window. {note}", 1
    by_type: dict[str, int] = {}
    for e in events:
        by_type[e.get("type", "?")] = by_type.get(e.get("type", "?"), 0) + 1
    newest, oldest = events[0], events[-1]
    top = ", ".join(f"{t}×{n}" for t, n in sorted(by_type.items(), key=lambda kv: -kv[1])[:5])
    lines = [
        f"{len(events)} recent public events for {a['login']}, from {_d(oldest.get('created_at'))} "
        f"to {_d(newest.get('created_at'))}: {top}",
        f"most recent: {newest.get('type')} on {(newest.get('repo') or {}).get('name', '?')} "
        f"at {_d(newest.get('created_at'))}",
        note,
    ]
    return "\n".join(lines), 1
