"""OSV vulnerability database (api.osv.dev) — free, keyless.

Repo-level GitHub advisories are often unpublished even for CVE'd projects,
so OSV is the reliable chain: manifest -> package name -> osv_query. It also
supports query-by-commit, which can flag a malicious commit directly.
"""

from __future__ import annotations

import httpx

OSV_URL = "https://api.osv.dev/v1/query"
MAX_VULNS = 10


def _severity(v: dict) -> str:
    for s in v.get("severity", []):
        if s.get("type") == "CVSS_V3":
            return f"CVSS3 {s.get('score')}"
    db = v.get("database_specific", {})
    return db.get("severity", "severity unknown")


def _ranges(v: dict) -> str:
    parts = []
    for aff in v.get("affected", [])[:3]:
        for rng in aff.get("ranges", [])[:2]:
            events = rng.get("events", [])
            intro = next((e["introduced"] for e in events if "introduced" in e), None)
            fixed = next((e["fixed"] for e in events if "fixed" in e), None)
            seg = f"introduced {intro or '?'}"
            seg += f", fixed {fixed}" if fixed else ", no fix listed"
            parts.append(seg)
        if aff.get("versions") and not aff.get("ranges"):
            vs = aff["versions"]
            parts.append(f"affected versions: {', '.join(vs[:5])}{'…' if len(vs) > 5 else ''}")
    return "; ".join(parts) or "affected ranges not listed"


def osv_query(_gh, a: dict) -> tuple[str, int]:
    query: dict = {}
    if a.get("commit"):
        query["commit"] = a["commit"]
        target = f"commit {a['commit'][:12]}"
    elif a.get("package"):
        query["package"] = {"name": a["package"], "ecosystem": a.get("ecosystem", "npm")}
        if a.get("version"):
            query["version"] = a["version"]
        target = f"{a.get('ecosystem', 'npm')} package '{a['package']}'" + (f" @ {a['version']}" if a.get("version") else "")
    else:
        return "ERROR (bad_arguments): osv_query needs either a package name or a commit sha.", 0

    try:
        resp = httpx.post(OSV_URL, json=query, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        return f"ERROR (osv_unreachable): could not query OSV ({exc.__class__.__name__}).", 1

    vulns = data.get("vulns", [])
    if not vulns:
        return f"OSV: no known vulnerabilities recorded for {target}.", 1

    lines = [f"OSV: {len(vulns)} known vulnerabilities for {target}:"]
    for v in vulns[:MAX_VULNS]:
        aliases = ", ".join(v.get("aliases", [])) or "no aliases"
        summary = (v.get("summary") or v.get("details") or "")[:200].replace("\n", " ")
        lines.append(f"- {v.get('id')} ({aliases}) [{_severity(v)}] published {(v.get('published') or '?')[:10]}")
        lines.append(f"  {summary}")
        lines.append(f"  {_ranges(v)}")
    if len(vulns) > MAX_VULNS:
        lines.append(f"...[{len(vulns) - MAX_VULNS} more vulnerabilities not shown]")
    return "\n".join(lines), 1
