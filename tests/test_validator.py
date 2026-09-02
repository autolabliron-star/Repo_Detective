"""The anti-folklore gate: fabricated evidence must be rejected."""

import unittest

from detective.validator import check_evidence, invalid_citations

LOG = [
    {"id": 1, "tool": "list_contributors", "observation": "top 10 of 30 listed contributors:\n- RIAEvangelist: 2891 commits (94.7%)"},
    {"id": 2, "tool": "osv_query", "observation": "OSV: 2 known vulnerabilities for npm package 'node-ipc':\n- GHSA-97m3 (CVE-2022-23812) [CVSS3 9.8]"},
]


class TestEvidenceValidation(unittest.TestCase):
    def test_verbatim_quote_passes(self):
        errors, annotated = check_evidence(
            [{"claim": "one maintainer dominates", "step_id": 1, "data_point": "RIAEvangelist: 2891 commits (94.7%)"}], LOG)
        self.assertEqual(errors, [])
        self.assertTrue(annotated[0]["verified"])

    def test_case_and_whitespace_normalized(self):
        errors, _ = check_evidence(
            [{"claim": "cve exists", "step_id": 2, "data_point": "cve-2022-23812)  [cvss3 9.8]"}], LOG)
        self.assertEqual(errors, [])

    def test_fabricated_quote_rejected(self):
        errors, annotated = check_evidence(
            [{"claim": "protestware shipped", "step_id": 1,
              "data_point": "the maintainer shipped destructive protestware in March 2022"}], LOG)
        self.assertEqual(len(errors), 1)
        self.assertFalse(annotated[0]["verified"])
        self.assertIn("does not contain", errors[0])

    def test_nonexistent_step_rejected(self):
        errors, _ = check_evidence([{"claim": "x", "step_id": 99, "data_point": "RIAEvangelist: 2891 commits"}], LOG)
        self.assertIn("does not exist", errors[0])

    def test_too_short_quote_rejected(self):
        errors, _ = check_evidence([{"claim": "x", "step_id": 1, "data_point": "2891"}], LOG)
        self.assertIn("too short", errors[0])

    def test_empty_evidence_rejected(self):
        errors, _ = check_evidence([], LOG)
        self.assertIn("empty", errors[0])

    # --- elisions: "start ... end" is accepted when every fragment is verbatim and in order ---

    def test_ellipsis_fragments_in_order_pass(self):
        errors, annotated = check_evidence(
            [{"claim": "critical CVE", "step_id": 2,
              "data_point": "OSV: 2 known vulnerabilities ... [CVSS3 9.8]"}], LOG)
        self.assertEqual(errors, [])
        self.assertTrue(annotated[0]["verified"])

    def test_unicode_and_bracketed_ellipses_pass(self):
        for quote in ("OSV: 2 known vulnerabilities … CVE-2022-23812",
                      "OSV: 2 known vulnerabilities [...] CVE-2022-23812",
                      "OSV: 2 known vulnerabilities (...) CVE-2022-23812"):
            errors, _ = check_evidence([{"claim": "cve", "step_id": 2, "data_point": quote}], LOG)
            self.assertEqual(errors, [], quote)

    def test_fragments_out_of_order_rejected(self):
        errors, annotated = check_evidence(
            [{"claim": "cve", "step_id": 2, "data_point": "[CVSS3 9.8] ... OSV: 2 known vulnerabilities"}], LOG)
        self.assertEqual(len(errors), 1)
        self.assertFalse(annotated[0]["verified"])
        self.assertIn("in order", errors[0])

    def test_fabricated_fragment_rejected(self):
        errors, _ = check_evidence(
            [{"claim": "protestware", "step_id": 2,
              "data_point": "OSV: 2 known vulnerabilities ... protestware shipped"}], LOG)
        self.assertEqual(len(errors), 1)
        self.assertIn('fragment "protestware shipped"', errors[0])

    def test_fragment_too_short_rejected(self):
        errors, _ = check_evidence(
            [{"claim": "cve", "step_id": 2, "data_point": "OSV: 2 known vulnerabilities ... 9.8"}], LOG)
        self.assertEqual(len(errors), 1)
        self.assertIn("too short", errors[0])

    def test_chat_citations(self):
        self.assertEqual(invalid_citations("see [step 1] and [step 7]", LOG), [7])
        self.assertEqual(invalid_citations("see [step 2]", LOG), [])
        self.assertEqual(invalid_citations("supported by [steps 1, 2] and [steps 2, 9]", LOG), [9])


if __name__ == "__main__":
    unittest.main()
