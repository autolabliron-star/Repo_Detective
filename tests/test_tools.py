"""Tool trimmers: what the agent actually sees. Two regressions from the first live run —
a JSON file rendered as a Python dict repr, and a case-sensitive 404 (`README.md` vs
`Readme.md`) that the agent turned into the finding "this project has no README"."""

import unittest

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


if __name__ == "__main__":
    unittest.main()
