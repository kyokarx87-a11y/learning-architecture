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


def record(**changes):
    rec = dict(at="2026-10-24T10:00:00+09:00", subject="math", unit="数列",
               problem_id="a", outcome="correct", teacher_eval="◎", self_eval="◎",
               stumble="none", hints=0)
    rec.update(changes)
    return rec


class ReviewRegressions(unittest.TestCase):
    def test_direct_add_during_hinted_session_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            state, history, pool = (root / n for n in ("custom.json", "ledger.jsonl", "pool.txt"))
            pool.write_text("a\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                session.main(["--state", str(state), "start", "--ledger", str(history),
                              "--pool", str(pool), "--subject", "math", "--unit", "数列"])
                for _ in range(2):
                    session.main(["--state", str(state), "hint"])
                before = state.read_bytes()
                with self.assertRaises(SystemExit) as raised:
                    ledger.main(["add", "--ledger", str(history), "--subject", "math", "--unit", "数列",
                                 "--problem-id", "a", "--outcome", "correct", "--teacher-eval", "◎",
                                 "--self-eval", "◎", "--stumble", "none"])
                self.assertNotEqual(raised.exception.code, 0)
                self.assertFalse(history.exists())
                self.assertEqual(state.read_bytes(), before)
                session.main(["--state", str(state), "finish", "--outcome", "correctWithHints",
                              "--teacher-eval", "△", "--self-eval", "◎", "--stumble", "execution",
                              "--error-category", "計算ミス"])
            self.assertEqual(len(ledger.load(history)), 1)

    def test_contradictions_are_rejected_by_shared_validator(self):
        bad = [record(outcome="correctWithHints", hints=2, stumble="execution", error_category="計算ミス"),
               record(stumble="execution", teacher_eval="×", error_category="計算ミス"),
               record(teacher_eval="×"), record(hints=1),
               record(outcome="correctWithHints", teacher_eval="〇", stumble="approach", error_category="概念の誤解"),
               record(outcome="failed", teacher_eval="〇", stumble="approach", error_category="概念の誤解"),
               record(outcome="correctRetry", stumble="execution", error_category="計算ミス"),
               record(hints=True), record(hints=-1), record(hints=4)]
        for rec in bad:
            with self.subTest(rec=rec), self.assertRaises(ValueError):
                ledger.validate(rec, complete=True)

    def test_duplicate_attempt_id_is_rejected_but_new_attempt_is_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ledger.jsonl"
            ledger.append(path, record(attempt_id="attempt-1"))
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                ledger.append(path, record(attempt_id="attempt-1"))
            self.assertEqual(path.read_bytes(), before)
            ledger.append(path, record(attempt_id="attempt-2"))
            self.assertEqual(len(ledger.load(path)), 2)

    def test_duplicate_ids_in_existing_ledger_fail_with_line_number(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ledger.jsonl"
            line = json.dumps(record(attempt_id="same")) + "\n"
            path.write_text(line * 2, encoding="utf-8")
            with self.assertRaises(SystemExit) as raised:
                ledger.load(path)
            self.assertIn(":2:", str(raised.exception))

    def test_valid_outcomes_and_independent_self_evaluation(self):
        for rec in (record(self_eval="×"), record(teacher_eval="〇"),
                    record(outcome="correctWithHints", hints=1, teacher_eval="〇", stumble="execution", error_category="計算ミス"),
                    record(outcome="correctWithHints", hints=2, teacher_eval="△", stumble="execution", error_category="計算ミス"),
                    record(outcome="correctRetry", teacher_eval="△", stumble="execution", error_category="計算ミス"),
                    record(outcome="failed", teacher_eval="×", stumble="approach", error_category="概念の誤解")):
            with self.subTest(rec=rec):
                ledger.validate(rec, complete=True)

    def test_missing_hint_count_is_not_invented_for_new_records(self):
        rec = record()
        del rec["hints"]
        ledger.validate(rec)  # 旧記録は読める
        with self.assertRaises(ValueError):
            ledger.validate(rec, complete=True)

    def test_finish_with_teacher_top_mark_after_hint_preserves_pending(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            state, history, pool = (root / n for n in ("state.json", "ledger.jsonl", "pool.txt"))
            pool.write_text("a\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                session.main(["--state", str(state), "start", "--ledger", str(history),
                              "--pool", str(pool), "--subject", "math", "--unit", "数列"])
                session.main(["--state", str(state), "hint"])
                before = state.read_bytes()
                args = ["--state", str(state), "finish", "--outcome", "correctWithHints",
                        "--self-eval", "◎", "--stumble", "execution", "--error-category", "計算ミス"]
                with self.assertRaises(SystemExit):
                    session.main(args + ["--teacher-eval", "◎"])
                self.assertEqual(state.read_bytes(), before)
                self.assertFalse(history.exists())
                session.main(args + ["--teacher-eval", "〇"])
            self.assertEqual(ledger.load(history)[0]["hints"], 1)

    def test_report_separates_attempts_first_and_latest_problem_results(self):
        rows = [record(outcome="failed", teacher_eval="×", stumble="approach", error_category="概念の誤解"),
                record(), record(problem_id="b")]
        result = ledger.report(rows)
        self.assertIn("演習 3回 / 異なる問題 2問", result)
        self.assertIn("初回正答率 50%", result)
        self.assertIn("最新正答率 100%", result)


if __name__ == "__main__":
    unittest.main()
