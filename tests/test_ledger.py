import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import ledger  # noqa: E402
from select_candidates import candidates  # noqa: E402


def rows(outcomes):
    return [{"outcome": o, "unit": "数列", "problem_id": f"p{i}"} for i, o in enumerate(outcomes)]


class LevelTest(unittest.TestCase):
    def test_under_ten_is_not_judged(self):
        self.assertIn("判定なし", ledger.suggest_level(rows(["failed"] * 9)))

    def test_boundary_70_percent_is_kept(self):  # 「未満」は境界を含まない
        self.assertIn("現状維持", ledger.suggest_level(rows(["correct"] * 7 + ["failed"] * 3)))

    def test_below_thresholds(self):
        self.assertIn("1段階", ledger.suggest_level(rows(["correct"] * 6 + ["failed"] * 4)))
        self.assertIn("2段階", ledger.suggest_level(rows(["correct"] * 4 + ["failed"] * 6)))
        self.assertIn("3段階", ledger.suggest_level(rows(["correct"] * 2 + ["failed"] * 8)))
        self.assertIn("1学年", ledger.suggest_level(rows(["failed"] * 10)))

    def test_only_last_ten_count(self):
        self.assertIn("現状維持", ledger.suggest_level(rows(["failed"] * 5 + ["correct"] * 10)))


class RecordTest(unittest.TestCase):
    def test_invalid_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(SystemExit):
            ledger.main(["add", "--ledger", str(Path(d) / "l.jsonl"), "--subject", "math",
                         "--unit", "u", "--problem-id", "p", "--outcome", "maybe",
                         "--teacher-eval", "◎", "--self-eval", "◎", "--stumble", "none"])

    def test_add_and_load(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "l.jsonl"
            ledger.main(["add", "--ledger", str(path), "--subject", "math", "--unit", "u",
                         "--problem-id", "p", "--outcome", "correct", "--self-eval", "◎",
                         "--teacher-eval", "◎", "--stumble", "none"])
            self.assertEqual(ledger.load(path)[0]["self_eval"], "◎")


class SelectTest(unittest.TestCase):
    def test_fresh_first_then_review(self):
        done = [{"unit": "数列", "problem_id": "a", "teacher_eval": "△"},
                {"unit": "数列", "problem_id": "b", "teacher_eval": "◎"}]
        self.assertEqual(candidates(["a", "b", "c"], done, "数列", 5), ["c"])
        self.assertEqual(candidates(["a", "b"], done, "数列", 5), ["a"])


if __name__ == "__main__":
    unittest.main()
