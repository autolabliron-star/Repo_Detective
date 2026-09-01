"""URL parsing accepts the forms people actually paste."""

import unittest

from detective.intake import parse_repo_url


class TestParseRepoUrl(unittest.TestCase):
    def test_forms(self):
        cases = {
            "https://github.com/expressjs/express": ("expressjs", "express"),
            "https://github.com/expressjs/express/": ("expressjs", "express"),
            "https://github.com/expressjs/express.git": ("expressjs", "express"),
            "https://github.com/expressjs/express/tree/master/lib": ("expressjs", "express"),
            "http://www.github.com/request/request": ("request", "request"),
            "git@github.com:RIAEvangelist/node-ipc.git": ("RIAEvangelist", "node-ipc"),
            "github.com/expressjs/express": ("expressjs", "express"),
            "expressjs/express": ("expressjs", "express"),
        }
        for text, expected in cases.items():
            self.assertEqual(parse_repo_url(text), expected, text)

    def test_garbage_rejected(self):
        for bad in ("", "https://github.com/", "just-a-word", "https://gitlab.com/x"):
            with self.assertRaises(ValueError, msg=bad):
                parse_repo_url(bad)


if __name__ == "__main__":
    unittest.main()
