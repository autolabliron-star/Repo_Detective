"""Tool trimmers: what the agent actually sees. Two regressions from the first live run —
a JSON file rendered as a Python dict repr, and a case-sensitive 404 (`README.md` vs
`Readme.md`) that the agent turned into the finding "this project has no README"."""

import unittest

import httpx

from detective.github_client import GitHubClient
from detective.tools.github import get_file


class DirGH:
    """package.json parsed to a dict by the gateway; README.md missing but Readme.md present."""

    def get(self, path, params=None, accept=None):
        if path.endswith("/contents/package.json"):
            return {"ok": True, "api_requests": 1, "data": {"name": "express", "version": "5.2.1"}}
        if path.endswith("/contents/README.md"):
            return {"ok": False, "api_requests": 1, "error": "not_found", "message": "Not Found"}
        if path.endswith("/contents/"):
            return {"ok": True, "api_requests": 1, "data": [
                {"name": "Readme.md"}, {"name": "package.json"}, {"name": "lib"}]}
        return {"ok": False, "api_requests": 1, "error": "not_found", "message": "Not Found"}


class TestGetFile(unittest.TestCase):
    def test_json_object_rendered_as_json(self):
        obs, n = get_file(DirGH(), {"owner": "o", "repo": "r", "path": "package.json"})
        self.assertIn('"name": "express"', obs)
        self.assertNotIn("{'name'", obs)
        self.assertEqual(n, 1)

    def test_404_lists_directory_and_suggests_case_fix(self):
        obs, n = get_file(DirGH(), {"owner": "o", "repo": "r", "path": "README.md"})
        self.assertTrue(obs.startswith("ERROR (not_found)"))
        self.assertIn("Did you mean Readme.md", obs)
        self.assertIn("Directory '/' contains: Readme.md, package.json, lib", obs)
        self.assertEqual(n, 2)


class TestClientBodyParsing(unittest.TestCase):
    def test_raw_markdown_is_text_despite_json_media_type(self):
        """Regression: GitHub labels raw file contents 'application/vnd.github.raw+json' even for
        Markdown; parsing that as JSON crashed get_file on every README in the first live run."""
        def handler(request):
            return httpx.Response(200, content=b"# Express\n\nFast, unopinionated",
                                  headers={"content-type": "application/vnd.github.raw+json; charset=utf-8"})
        gh = GitHubClient(cache_dir=None)
        gh._http = httpx.Client(transport=httpx.MockTransport(handler))
        res = gh.get("/repos/o/r/contents/Readme.md", accept="application/vnd.github.raw+json")
        self.assertTrue(res["ok"])
        self.assertEqual(res["data"], "# Express\n\nFast, unopinionated")
        obs, _ = get_file(gh, {"owner": "o", "repo": "r", "path": "Readme.md"})
        self.assertIn("Fast, unopinionated", obs)


class TestEmptyRepository(unittest.TestCase):
    """Grace under fire: a repository with no commits answers 409 on /commits and 204 on /contributors.
    Both must become observations the agent can reason about, never exceptions."""

    def _gh(self):
        def handler(request):
            if request.url.path.endswith("/commits"):
                return httpx.Response(409, json={"message": "Git Repository is empty."})
            if request.url.path.endswith("/contributors"):
                return httpx.Response(204)
            return httpx.Response(404, json={"message": "Not Found"})
        gh = GitHubClient(cache_dir=None)
        gh._http = httpx.Client(transport=httpx.MockTransport(handler))
        return gh

    def test_empty_repo_is_an_observation_not_a_crash(self):
        from detective.tools.github import list_commits, list_contributors
        obs, _ = list_commits(self._gh(), {"owner": "o", "repo": "r"})
        self.assertTrue(obs.startswith("ERROR (empty_repository)"), obs)
        self.assertIn("empty", obs.lower())
        obs2, _ = list_contributors(self._gh(), {"owner": "o", "repo": "r"})
        self.assertIn("no contributors listed", obs2)


if __name__ == "__main__":
    unittest.main()
