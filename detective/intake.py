"""Intake — plain code, no LLM.

Input: a repository URL (or owner/repo). Output: the clean starting point the
agent receives — basic facts, plus a failure taxonomy handled up front:
404 / DMCA / rate-limited exit cleanly before any LLM budget is spent, while
archived / disabled / renamed / empty are FINDINGS the agent should see, not
reasons to stop.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .github_client import GitHubClient

_URL_RE = re.compile(
    r"^(?:https?://(?:www\.)?github\.com/|git@github\.com:)?"
    r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?(?:/.*)?$"
)


def parse_repo_url(text: str) -> tuple[str, str]:
    """Accepts https://github.com/owner/repo[.git][/anything], git@ form, or bare owner/repo."""
    text = text.strip().rstrip("/")
    if text.startswith(("github.com/", "www.github.com/")):
        text = "https://" + text
    m = _URL_RE.match(text)
    if not m or "github.com" in m.group("owner"):
        raise ValueError(f"could not parse a GitHub owner/repo out of: {text!r}")
    return m.group("owner"), m.group("repo")


def run_intake(gh: GitHubClient, url: str) -> tuple[dict | None, str | None]:
    """Returns (intake, None) on success or (None, fatal_message) when there is
    nothing to investigate (404, DMCA, quota exhausted, network down)."""
    try:
        owner, repo = parse_repo_url(url)
    except ValueError as exc:
        return None, str(exc)

    res = gh.get(f"/repos/{owner}/{repo}")
    if not res["ok"]:
        reasons = {
            "not_found": f"GitHub returned 404 for {owner}/{repo} — the repository does not exist or is private. Nothing to investigate.",
            "unavailable_legal": f"{owner}/{repo} is unavailable for legal reasons (HTTP 451 / DMCA takedown). That itself is a strong supply-chain signal, but there is no data to investigate.",
            "rate_limited": f"{res['message']}." + (f" Quota resets {res.get('resets_at')} — retry then, or set GITHUB_TOKEN." if res.get("resets_at") else ""),
            "network": f"cannot reach GitHub: {res['message']}",
            "bad_credentials": res["message"],
        }
        return None, reasons.get(res["error"], f"GitHub error ({res['error']}): {res['message']}")

    data = res["data"]
    canonical = data["full_name"]
    requested = f"{owner}/{repo}"
    renamed = canonical.lower() != requested.lower()

    warnings: list[str] = []
    if renamed:
        warnings.append(f"repository was moved/renamed: {requested} -> {canonical}")
    if data.get("archived"):
        warnings.append("repository is ARCHIVED (read-only) — no future fixes or security patches will land here")
    if data.get("disabled"):
        warnings.append("repository is DISABLED by GitHub")
    if data.get("fork"):
        parent = (data.get("parent") or {}).get("full_name")
        warnings.append(f"this repository is itself a fork{f' of {parent}' if parent else ''}")
    if data.get("size", 0) == 0:
        warnings.append("repository size is 0 KB — it may be empty")

    # Last release, with a tags fallback (many projects never cut GitHub Releases).
    last_release = None
    release_note = "no GitHub releases"
    rel = gh.get(f"/repos/{canonical}/releases", params={"per_page": 1})
    if rel["ok"] and rel["data"]:
        r = rel["data"][0]
        last_release = {"tag": r.get("tag_name"), "name": r.get("name"), "published_at": r.get("published_at")}
        release_note = f"latest release {r.get('tag_name')} on {(r.get('published_at') or '')[:10]}"
    else:
        tags = gh.get(f"/repos/{canonical}/tags", params={"per_page": 1})
        if tags["ok"] and tags["data"]:
            release_note = f"no GitHub releases, but tags exist (latest tag: {tags['data'][0].get('name')})"

    # Top contributors with share of the top-30 commit total (bus-factor signal).
    top_contributors: list[dict] = []
    contributors_note = ""
    con = gh.get(f"/repos/{canonical}/contributors", params={"per_page": 30})
    if con["ok"] and isinstance(con["data"], list) and con["data"]:
        total = sum(c.get("contributions", 0) for c in con["data"]) or 1
        for c in con["data"][:10]:
            top_contributors.append({
                "login": c.get("login", "?"),
                "commits": c.get("contributions", 0),
                "share_pct": round(100.0 * c.get("contributions", 0) / total, 1),
            })
        contributors_note = f"shares computed over the top {len(con['data'])} contributors' commit total"
    elif con["ok"]:
        contributors_note = "no contributors listed (repository may be empty)"
        warnings.append("no contributors listed")
    else:
        contributors_note = f"could not fetch contributors ({con['error']}: {con['message']})"
        warnings.append(contributors_note)

    quota = gh.quota()
    if not quota["authenticated"] and quota["remaining"] is not None and quota["remaining"] < 40:
        warnings.append(
            f"low GitHub anonymous quota: {quota['remaining']} requests left (resets {quota['resets_at']}); "
            "a full investigation needs ~40 — expect rate-limit errors mid-way and conclude on what you can verify "
            "(a free GITHUB_TOKEN in .env raises the limit to 5,000/h)"
        )

    intake = {
        "input_url": url,
        "canonical_full_name": canonical,
        "renamed_from": requested if renamed else None,
        "owner": canonical.split("/")[0],
        "repo": canonical.split("/")[1],
        "description": data.get("description"),
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "open_issues_and_prs": data.get("open_issues_count"),
        "language": data.get("language"),
        "license": (data.get("license") or {}).get("spdx_id"),
        "created_at": data.get("created_at"),
        "pushed_at": data.get("pushed_at"),
        "default_branch": data.get("default_branch"),
        "archived": data.get("archived", False),
        "disabled": data.get("disabled", False),
        "is_fork": data.get("fork", False),
        "fork_parent": (data.get("parent") or {}).get("full_name"),
        "size_kb": data.get("size"),
        "last_release": last_release,
        "release_note": release_note,
        "top_contributors": top_contributors,
        "contributors_note": contributors_note,
        "warnings": warnings,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return intake, None
