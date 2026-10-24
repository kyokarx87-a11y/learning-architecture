#!/usr/bin/env python3
"""演習台帳（JSON Lines）の記録と集計。標準ライブラリのみ。

    python ledger.py add --ledger L.jsonl --subject math --unit 数列 --problem-id P1 --outcome correct
    python ledger.py report   --ledger L.jsonl   # 単元別の件数・正答率と、直近10問によるレベル提案
    python ledger.py diagnose --ledger L.jsonl   # 躓いた段・誤答の種類・自己評価と教師評価のずれ
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUTCOMES = ("correct", "correctWithHints", "correctRetry", "failed")
CORRECT = {"correct", "correctWithHints"}  # 正答＝1回目の解答で正解（ヒント使用は可）
MARKS = ("◎", "〇", "△", "×")  # 復習の必要度（◎＝低い 〜 ×＝高い）
STAGES = ("none", "reading", "approach", "execution", "verification")
ERRORS = ("計算ミス", "公式の未定着", "公式の誤適用", "単位の取り違え", "概念の誤解")
JST = timezone(timedelta(hours=9))


def load(path: Path) -> list[dict]:
    """台帳を読む。壊れた行は黙って捨てず、行番号付きで報告して落とす。"""
    rows = []
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            sys.exit(f"{path}:{no} が JSON として読めない: {exc}")
    return rows


def append(path: Path, rec: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def make_record(a: argparse.Namespace) -> dict:
    """引数を検査して記録を作る。語彙の外の値は推測で通さず拒否する（Fail Loud）。"""
    checks = [("outcome", a.outcome, OUTCOMES), ("teacher_eval", a.teacher_eval, MARKS),
              ("self_eval", a.self_eval, MARKS), ("stumble", a.stumble, STAGES),
              ("error_category", a.error_category, ERRORS)]
    for name, val, vocab in checks:
        if val is not None and val not in vocab:
            sys.exit(f"{name} の値が不正: {val!r}（使える値: {', '.join(vocab)}）")
    rec = {"at": datetime.now(JST).isoformat(timespec="seconds"), "subject": a.subject,
           "unit": a.unit, "problem_id": a.problem_id, "outcome": a.outcome}
    for name, val, _ in checks[1:]:
        if val is not None:
            rec[name] = val
    return rec


def accuracy(rows: list[dict]) -> float:
    return sum(r["outcome"] in CORRECT for r in rows) / len(rows) if rows else 0.0


def suggest_level(rows: list[dict]) -> str:
    """直近10問の正答率から、レベル調整の提案を返す。10問未満なら判定しない。"""
    if len(rows) < 10:
        return f"判定なし（{len(rows)}問。10問たまるまで判定しない）"
    acc = accuracy(rows[-10:])
    if acc == 0:
        return "1学年落とす（正答率0%）"
    for limit, steps in ((0.3, 3), (0.5, 2), (0.7, 1)):
        if acc < limit:  # 「未満」は境界を含まない
            return f"{steps}段階落とす（正答率{acc:.0%}）"
    return f"現状維持（正答率{acc:.0%}）"


def report(rows: list[dict]) -> str:
    out = [f"記録 {len(rows)}問 / 全体の正答率 {accuracy(rows):.0%}", "", "単元別:"]
    for unit in dict.fromkeys(r["unit"] for r in rows):
        sub = [r for r in rows if r["unit"] == unit]
        out.append(f"  {unit}: {len(sub)}問, 正答率 {accuracy(sub):.0%}")
    out += ["", "レベル提案: " + suggest_level(rows)]
    return "\n".join(out)


def diagnose(rows: list[dict]) -> str:
    out = ["躓いた段（最初に落ちた段）:"]
    stages = Counter(r["stumble"] for r in rows if "stumble" in r)
    out += [f"  {s}: {stages[s]}件" for s in STAGES if stages[s]] or ["  記録なし"]
    out += ["", "誤答の種類:"]
    errs = Counter(r["error_category"] for r in rows if "error_category" in r)
    out += [f"  {e}: {errs[e]}件" for e in ERRORS if errs[e]] or ["  記録なし"]
    both = [r for r in rows if "self_eval" in r and "teacher_eval" in r]
    out += ["", f"自己評価と教師評価（両方そろった{len(both)}問）:"]
    if both:
        # 数値が大きいほど「復習が必要」。自己−教師が負なら、本人は楽観的（できたつもり）
        gap = [MARKS.index(r["self_eval"]) - MARKS.index(r["teacher_eval"]) for r in both]
        out.append(f"  一致 {gap.count(0)}問 / 本人が楽観的 {sum(g < 0 for g in gap)}問"
                   f" / 本人が慎重 {sum(g > 0 for g in gap)}問")
        for r, g in zip(both, gap):
            if g < 0:
                out.append(f"    ずれ: {r['problem_id']}（自己{r['self_eval']} / 教師{r['teacher_eval']}）")
    return "\n".join(out)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("add", "report", "diagnose"):
        p = sub.add_parser(name)
        p.add_argument("--ledger", type=Path, required=True)
        if name == "add":
            for k in ("subject", "unit", "problem-id", "outcome"):
                p.add_argument(f"--{k}", required=True)
            for k in ("teacher-eval", "self-eval", "stumble", "error-category"):
                p.add_argument(f"--{k}")
    a = ap.parse_args(argv)
    if a.cmd == "add":
        append(a.ledger, make_record(a))
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print((report if a.cmd == "report" else diagnose)(load(a.ledger)))


if __name__ == "__main__":
    main()
