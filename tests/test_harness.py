import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import ledger
import session
from select_candidates import candidates


def record(**changes):
    rec = dict(at="2026-10-24T10:00:00+09:00", subject="math", unit="数列",
               problem_id="a", outcome="correct", teacher_eval="◎", self_eval="◎", stumble="none")
    rec.update(changes)
    return rec


class SelectionTest(unittest.TestCase):
    def test_review_stays_in_pool_and_exact_scope(self):
        rows = [record(teacher_eval="△"), record(problem_id="outside", teacher_eval="×"),
                record(problem_id="b", unit="数列応用", teacher_eval="×"),
                record(problem_id="c", subject="physics", teacher_eval="×")]
        self.assertEqual(candidates(["a"], rows, "数列", 5, "math"), ["a"])
        self.assertEqual(candidates(["b", "c"], rows, "数列", 5, "math"), ["b", "c"])

    def test_latest_result_and_unique_pool(self):
        rows = [record(teacher_eval="×"), record(teacher_eval="◎")]
        self.assertEqual(candidates(["a"], rows, "数列", 5, "math"), [])
        self.assertEqual(candidates(["a", "a"], [], "数列", 5, "math"), ["a"])

    def test_nonpositive_count(self):
        for count in (0, -1):
            with self.assertRaises(ValueError):
                candidates(["a"], [], "数列", count)


class IntegrityTest(unittest.TestCase):
    def test_invalid_records_fail_with_line_number(self):
        for bad in ([], {"outcome": "failed"}, record(outcome="typo"), record(at="yesterday"),
                    record(teacher_eval="OK"), record(at="2026-10-24T10:00:00")):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as d:
                p = Path(d) / "ledger.jsonl"
                p.write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaises(SystemExit) as raised:
                    ledger.load(p)
                self.assertIn(":1:", str(raised.exception))

    def test_incomplete_or_inconsistent_records_cannot_be_appended(self):
        incomplete = record()
        del incomplete["self_eval"]
        for bad in (incomplete, record(outcome="failed"), record(stumble="execution"),
                    record(error_category="計算ミス")):
            with self.assertRaises(ValueError):
                ledger.validate(bad, complete=True)

    def test_legacy_missing_diagnostics_are_reported(self):
        old = record()
        del old["self_eval"]
        ledger.validate(old)
        self.assertIn("不足した旧記録: 1問", ledger.diagnose([old]))
        self.assertIn("不足した旧記録: 1問", ledger.diagnose([record(stumble="execution")]))

    def test_condition_error_has_its_own_category(self):
        rec = record(outcome="failed", stumble="reading", error_category="条件の取り違え")
        ledger.validate(rec, complete=True)
        self.assertIn("条件の取り違え: 1件", ledger.diagnose([rec]))

    def test_corrupt_or_unterminated_ledger_is_not_extended(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ledger.jsonl"
            for content in ("bad\n", json.dumps(record())):
                p.write_text(content, encoding="utf-8")
                with self.assertRaises((ValueError, SystemExit)):
                    ledger.append(p, record())
                self.assertEqual(p.read_text(encoding="utf-8"), content)

    def test_level_windows_are_not_mixed_and_independent_rate_is_visible(self):
        rows = [record(outcome="failed", subject="physics") for _ in range(5)]
        rows += [record(unit="微分") for _ in range(5)]
        report = ledger.report(rows)
        self.assertEqual(report.count("判定なし（5問"), 2)
        self.assertIn("自力正答率", report)


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / "session.json"
        self.ledger = self.root / "ledger.jsonl"
        self.pool = self.root / "pool.txt"
        self.pool.write_text("a\nb\n", encoding="utf-8")

    def run_cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            session.main(["--state", str(self.state), *args])

    def start(self):
        self.run_cli("start", "--ledger", str(self.ledger), "--pool", str(self.pool),
                     "--subject", "math", "--unit", "数列")

    def finish(self, outcome="correct", **extra):
        args = ["finish", "--outcome", outcome, "--teacher-eval", "◎", "--self-eval", "〇",
                "--stumble", extra.pop("stumble", "none")]
        if "error" in extra:
            args += ["--error-category", extra["error"]]
        self.run_cli(*args)

    def test_unrecorded_problem_blocks_next_start_across_restart(self):
        self.start()
        before = self.state.read_text(encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.start()
        self.assertEqual(self.state.read_text(encoding="utf-8"), before)
        self.finish()
        self.start()
        self.assertEqual(session.read_state(self.state)["problem_id"], "b")
        self.assertEqual(ledger.load(self.ledger)[0]["self_eval"], "〇")

    def test_three_hints_only_and_no_false_independent_success(self):
        self.start()
        for _ in range(3):
            self.run_cli("hint")
        with self.assertRaises(SystemExit):
            self.run_cli("hint")
        with self.assertRaises(SystemExit):
            self.finish()
        self.assertFalse(self.ledger.exists())
        self.finish("correctWithHints", stumble="execution", error="計算ミス")
        self.assertEqual(ledger.load(self.ledger)[0]["hints"], 3)

    def test_missing_self_eval_blocks_finish_without_mutation(self):
        self.start()
        with self.assertRaises(SystemExit):
            self.run_cli("finish", "--outcome", "correct", "--teacher-eval", "◎", "--stumble", "none")
        self.assertFalse(self.ledger.exists())
        self.assertTrue(session.read_state(self.state))

    def test_interruption_after_append_recovers_without_duplicate(self):
        self.start()
        pending = session.read_state(self.state)
        ledger.append(self.ledger, record(attempt_id=pending["attempt_id"]))
        self.run_cli("status")
        self.assertEqual(session.read_state(self.state), {})
        with self.assertRaises(SystemExit):
            self.finish()
        self.assertEqual(len(ledger.load(self.ledger)), 1)

    def test_invalid_state_fails_closed(self):
        self.state.write_text('{"hints": 0}', encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.start()

    def test_state_cannot_overwrite_pool(self):
        self.pool.write_text("{}\n", encoding="utf-8")
        before = self.pool.read_text(encoding="utf-8")
        # 空状態としても読める問題IDで、startの同一パス検査を通す。
        self.state = self.pool
        with self.assertRaises(SystemExit):
            self.start()
        self.assertEqual(self.pool.read_text(encoding="utf-8"), before)

    def test_state_temp_cannot_overwrite_pool(self):
        self.pool = self.state.with_suffix(self.state.suffix + ".tmp")
        self.pool.write_text("a\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.start()
        self.assertEqual(self.pool.read_text(encoding="utf-8"), "a\n")


if __name__ == "__main__":
    unittest.main()
