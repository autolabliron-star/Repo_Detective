"""Budget invariants: used never exceeds granted, exhaustion raises, extensions extend."""

import tempfile
import unittest
from pathlib import Path

from detective.investigation import Investigation
from detective.llm import BudgetExhausted, check_budget

INTAKE = {"input_url": "x", "canonical_full_name": "owner/repo"}


def make_inv(budget=3):
    tmp = tempfile.mkdtemp()
    return Investigation.create(Path(tmp), INTAKE, budget_initial=budget)


class TestBudget(unittest.TestCase):
    def test_used_never_exceeds_granted(self):
        inv = make_inv(3)
        for _ in range(3):
            check_budget(inv)
            inv.count()
        self.assertEqual(inv.budget_used(), 3)
        self.assertEqual(inv.budget_remaining(), 0)
        with self.assertRaises(BudgetExhausted):
            check_budget(inv)

    def test_extension_extends(self):
        inv = make_inv(2)
        inv.count(); inv.count()
        with self.assertRaises(BudgetExhausted):
            check_budget(inv)
        inv.add_extension(requested=5, granted=5, argument="test", decided_by="human")
        self.assertEqual(inv.budget_remaining(), 5)
        check_budget(inv)  # no raise

    def test_denial_wrapup_call(self):
        inv = make_inv(1)
        inv.count()
        inv.add_extension(requested=10, granted=1, argument="denied — wrap-up only", decided_by="human (denied)")
        self.assertEqual(inv.budget_remaining(), 1)

    def test_count_persists(self):
        inv = make_inv(5)
        inv.count()
        reloaded = Investigation.load(inv.dir.parent, inv.dir.name)
        self.assertEqual(reloaded.budget_used(), 1)

    def test_uncounted_path(self):
        check_budget(None)  # chat Q&A passes budget=None — always allowed


if __name__ == "__main__":
    unittest.main()
