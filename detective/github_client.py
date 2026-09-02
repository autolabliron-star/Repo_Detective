"""Single HTTP layer for the GitHub REST API.

Every request in the project goes through GitHubClient.get():

- Freshness cache + ETag revalidation: responses are cached on disk. Within
  DETECTIVE_CACHE_TTL (default 60 min — the anonymous quota window) a cached
  response is served with ZERO HTTP requests, so re-running or re-tasking the
  same repos inside a grading session costs no quota at all. After
  the TTL, an If-None-Match revalidation keeps the cache correct. (Measured
  in practice: GitHub counts 304s against the anonymous quota, so freshness
  short-circuiting, not the ETag, is what protects the 60/h limit.)
- Rate-limit telemetry: remaining/reset read from every response.
- Rename handling: redirects are followed; the caller can see the final URL.
- Structured errors: 404 / 403 / 409 / 429 / 451 come back as dicts the agent
  can reason about — nothing in this module raises into the agent loop.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

API_ROOT = "https://api.github.com"


class GitHubClient:
    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir else None
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "repo-detective",
        }
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.authenticated = bool(token)
        self._http = httpx.Client(headers=headers, follow_redirects=True, timeout=30)
        self.requests_made = 0
        self.quota_remaining: int | None = None
        self.quota_reset: str | None = None
        self._simulate_limit = int(os.environ.get("DETECTIVE_SIMULATE_RATELIMIT", "0") or 0)
        self._cache_ttl = int(os.environ.get("DETECTIVE_CACHE_TTL", "3600") or 0)

    # ------------------------------------------------------------------ #

    def get(self, path: str, params: dict | None = None, accept: str | None = None) -> dict:
        """GET a GitHub API path (or full URL). Returns either
        {"ok": True, "data": ..., "final_url": ..., "from_cache": bool, "api_requests": 1}
        or
        {"ok": False, "error": <code>, "message": ..., "api_requests": 1}.
        """
        if self._simulate_limit and self.requests_made >= self._simulate_limit:
            return {
                "ok": False,
                "error": "rate_limited",
                "message": "GitHub rate limit exhausted (simulated via DETECTIVE_SIMULATE_RATELIMIT)",
                "resets_at": "simulation",
                "api_requests": 0,
            }

        url = path if path.startswith("http") else API_ROOT + path
        cached = self._cache_read(url, params, accept)
        if cached and self._is_fresh(cached):
            return {
                "ok": True,
                "data": cached["body"],
                "final_url": cached.get("final_url", url),
                "from_cache": True,
                "api_requests": 0,
            }
        headers = {}
        if accept:
            headers["Accept"] = accept
        if cached and cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]

        try:
            resp = self._http.get(url, params=params or {}, headers=headers)
        except httpx.HTTPError as exc:
            return {
                "ok": False,
                "error": "network",
                "message": f"network error reaching GitHub: {exc.__class__.__name__}",
                "api_requests": 0,
            }

        self.requests_made += 1
        self._read_quota(resp)

        if resp.status_code == 304 and cached:
            return {
                "ok": True,
                "data": cached["body"],
                "final_url": cached.get("final_url", url),
                "from_cache": True,
                "api_requests": 1,
            }
        if resp.status_code in (200, 201):
            body = self._parse_body(resp, accept)
            final_url = str(resp.url)
            self._cache_write(url, params, accept, resp.headers.get("etag"), body, final_url)
            return {
                "ok": True,
                "data": body,
                "final_url": final_url,
                "from_cache": False,
                "redirected": bool(resp.history),
                "api_requests": 1,
            }
        if resp.status_code == 204:  # e.g. /contributors on an empty repository
            return {"ok": True, "data": [], "final_url": str(resp.url), "from_cache": False, "api_requests": 1}
        return {"ok": False, **self._error_for(resp), "api_requests": 1}

    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_body(resp: httpx.Response, accept: str | None):
        """File contents requested with a raw media type come back labelled
        'application/vnd.github.raw+json' even when they are Markdown — treat raw as text.
        Everything else is JSON, but a parse failure degrades to text rather than raising."""
        if accept and "raw" in accept:
            return resp.text
        if "json" in resp.headers.get("content-type", ""):
            try:
                return resp.json()
            except ValueError:
                return resp.text
        return resp.text

    def quota(self) -> dict:
        return {
            "remaining": self.quota_remaining,
            "resets_at": self.quota_reset,
            "authenticated": self.authenticated,
        }

    def quota_line(self) -> str:
        if self.quota_remaining is None:
            return "GitHub quota: unknown"
        kind = "authenticated" if self.authenticated else "anonymous"
        line = f"GitHub {kind} quota: {self.quota_remaining} requests left"
        if self.quota_reset:
            line += f", resets {self.quota_reset}"
        return line

    def _read_quota(self, resp: httpx.Response) -> None:
        remaining = resp.headers.get("x-ratelimit-remaining")
        reset = resp.headers.get("x-ratelimit-reset")
        if remaining is not None:
            try:
                self.quota_remaining = int(remaining)
            except ValueError:
                pass
        if reset:
            try:
                dt = datetime.fromtimestamp(int(reset), tz=timezone.utc)
                self.quota_reset = dt.strftime("%H:%M UTC")
            except ValueError:
                pass

    def _error_for(self, resp: httpx.Response) -> dict:
        code = resp.status_code
        try:
            msg = resp.json().get("message", "")
        except Exception:
            msg = resp.text[:200]
        if code in (403, 429) and resp.headers.get("x-ratelimit-remaining") == "0":
            hint = "" if self.authenticated else " (anonymous quota is 60/h; an optional GITHUB_TOKEN raises it to 5000/h)"
            return {
                "error": "rate_limited",
                "message": f"GitHub rate limit exhausted{hint}",
                "resets_at": self.quota_reset,
            }
        if code == 404:
            return {"error": "not_found", "message": msg or "not found (repository may not exist or is private)"}
        if code == 409:
            return {"error": "empty_repository", "message": msg or "the git repository is empty"}
        if code == 451:
            return {"error": "unavailable_legal", "message": msg or "repository unavailable for legal reasons (DMCA)"}
        if code == 401:
            return {"error": "bad_credentials", "message": "the provided GITHUB_TOKEN was rejected (401)"}
        return {"error": f"http_{code}", "message": msg or f"unexpected HTTP {code}"}

    # ---------------------------- cache ------------------------------- #

    def _is_fresh(self, cached: dict) -> bool:
        if not self._cache_ttl:
            return False
        try:
            fetched = datetime.fromisoformat(cached["fetched_at"])
        except (KeyError, ValueError):
            return False
        return (datetime.now(timezone.utc) - fetched).total_seconds() < self._cache_ttl

    def _cache_key(self, url: str, params: dict | None, accept: str | None) -> str:
        raw = json.dumps({"url": url, "params": params or {}, "accept": accept or ""}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def _cache_read(self, url: str, params: dict | None, accept: str | None) -> dict | None:
        if not self.cache_dir:
            return None
        path = self.cache_dir / f"{self._cache_key(url, params, accept)}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def _cache_write(self, url, params, accept, etag, body, final_url) -> None:
        if not self.cache_dir:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            path = self.cache_dir / f"{self._cache_key(url, params, accept)}.json"
            path.write_text(json.dumps({
                "url": url,
                "params": params or {},
                "accept": accept,
                "etag": etag,
                "final_url": final_url,
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "body": body,
            }))
        except OSError:
            pass  # cache is best-effort; never let it break a request
