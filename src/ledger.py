#!/usr/bin/env python3
"""演習台帳（JSON Lines）の記録と集計。標準ライブラリのみ。

    記録は session.py finish から行う（直接 add は廃止）。
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
ERRORS = ("計算ミス", "公式の未定着", "公式の誤適用", "単位の取り違え", "条件の取り違え", "概念の誤解")
JST = timezone(timedelta(hours=9))


def validate(rec: dict, complete: bool = False) -> None:
    """旧台帳は任意の評価を許す。新しい記録は診断項目を必須にする。"""
    if not isinstance(rec, dict):
        raise ValueError("記録はオブジェクトにしてください")
    for key in ("at", "subject", "unit", "problem_id", "outcome"):
        if not isinstance(rec.get(key), str) or not rec[key].strip():
            raise ValueError(f"{key} は空でない文字列が必要です")
    try:
        stamp = datetime.fromisoformat(rec["at"])
    except ValueError:
        raise ValueError("at は ISO 8601 日時が必要です") from None
    if stamp.utcoffset() is None:
        raise ValueError("at にはタイムゾーンが必要です")
    for key, vocab in (("outcome", OUTCOMES), ("teacher_eval", MARKS),
                       ("self_eval", MARKS), ("stumble", STAGES), ("error_category", ERRORS)):
        if key in rec and rec[key] not in vocab:
            raise ValueError(f"{key} の値が不正: {rec[key]!r}")
    if "attempt_id" in rec and (not isinstance(rec["attempt_id"], str) or not rec["attempt_id"].strip()):
        raise ValueError("attempt_id は空でない文字列が必要です")
    if "hints" in rec and (type(rec["hints"]) is not int or not 0 <= rec["hints"] <= 3):
        raise ValueError("hints は0〜3の整数が必要です")
    if complete:
        for key in ("teacher_eval", "self_eval", "stumble", "hints"):
            if key not in rec:
                raise ValueError(f"{key} が必要です。自己評価は本人の回答を待ってください")
        if rec["outcome"] != "correct" and rec["stumble"] == "none":
            raise ValueError("ヒント・再解答・未達では躓いた段が必要です")
        if rec["stumble"] != "none" and "error_category" not in rec:
            raise ValueError("躓きがある場合は error_category が必要です")
        if rec["stumble"] == "none" and "error_category" in rec:
            raise ValueError("躓きなしの記録に error_category は付けられません")
        if rec["outcome"] == "correct":
            if rec["hints"] or rec["stumble"] != "none" or rec["teacher_eval"] == "×":
                raise ValueError("correct はヒント0回・躓きなし・教師評価×以外が必要です")
        elif rec["teacher_eval"] == "◎":
            raise ValueError("教師評価◎はヒントなしの初回自力正解に限ります")
        if rec["outcome"] == "correctWithHints" and not rec["hints"]:
            raise ValueError("correctWithHints はヒント1〜3回が必要です")
        if rec["outcome"] == "failed" and rec["teacher_eval"] != "×":
            raise ValueError("未達の failed は教師評価×が必要です")
        if rec["hints"] >= 2 and rec["teacher_eval"] == "〇":
            raise ValueError("複数回のヒント使用は教師評価△または×が必要です")


def load(path: Path) -> list[dict]:
    """台帳を読む。壊れた行は黙って捨てず、行番号付きで報告して落とす。"""
    rows = []
    attempts = set()
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            validate(rec)
            attempt_id = rec.get("attempt_id")
            if attempt_id is not None:
                if attempt_id in attempts:
                    raise ValueError(f"attempt_id が重複しています: {attempt_id}")
                attempts.add(attempt_id)
            rows.append(rec)
        except ValueError as exc:
            sys.exit(f"{path}:{no}: {exc}")
    return rows


def append(path: Path, rec: dict) -> None:
    validate(rec, complete=True)
    if path.exists():
        rows = load(path)  # 壊れた台帳への追記で被害を広げない
        if rec.get("attempt_id") is not None and any(r.get("attempt_id") == rec["attempt_id"] for r in rows):
            raise ValueError("同じ attempt_id の二重追記はできません")
        if path.stat().st_size:
            with path.open("rb") as f:
                f.seek(-1, 2)
                if f.read(1) != b"\n":
                    raise ValueError("台帳末尾に改行がありません。追記前に確認してください")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def make_record(a: argparse.Namespace, hints: int) -> dict:
    """引数を検査して記録を作る。語彙の外の値は推測で通さず拒否する（Fail Loud）。"""
    checks = [("outcome", a.outcome, OUTCOMES), ("teacher_eval", a.teacher_eval, MARKS),
              ("self_eval", a.self_eval, MARKS), ("stumble", a.stumble, STAGES),
              ("error_category", a.error_category, ERRORS)]
    for name, val, vocab in checks:
        if val is not None and val not in vocab:
            sys.exit(f"{name} の値が不正: {val!r}（使える値: {', '.join(vocab)}）")
    rec = {"at": datetime.now(JST).isoformat(timespec="seconds"), "subject": a.subject,
           "unit": a.unit, "problem_id": a.problem_id, "outcome": a.outcome, "hints": hints}
    for name, val, _ in checks[1:]:
        if val is not None:
            rec[name] = val
    try:
        validate(rec, complete=True)
    except ValueError as exc:
        sys.exit(str(exc))
    return rec


def accuracy(rows: list[dict]) -> float:
    return sum(r["outcome"] in CORRECT for r in rows) / len(rows) if rows else 0.0


def suggest_level(rows: list[dict]) -> str:
    """直近10演習回の正答率から提案する。再演習を含む。10回未満なら判定しない。"""
    if len(rows) < 10:
        return f"判定なし（{len(rows)}回。10回たまるまで判定しない）"
    acc = accuracy(rows[-10:])
    if acc == 0:
        return "1学年落とす（正答率0%）"
    for limit, steps in ((0.3, 3), (0.5, 2), (0.7, 1)):
        if acc < limit:  # 「未満」は境界を含まない
            return f"{steps}段階落とす（正答率{acc:.0%}）"
    return f"現状維持（正答率{acc:.0%}）"


def report(rows: list[dict]) -> str:
    first, latest = {}, {}
    for rec in rows:
        key = (rec["subject"], rec["unit"], rec["problem_id"])
        first.setdefault(key, rec)
        latest[key] = rec
    out = [f"演習 {len(rows)}回 / 異なる問題 {len(first)}問 / 演習回ごとの正答率 {accuracy(rows):.0%}",
           f"問題別の初回正答率 {accuracy(list(first.values())):.0%}"
           f" / 最新正答率 {accuracy(list(latest.values())):.0%}", "", "単元別:"]
    for subject, unit in dict.fromkeys((r["subject"], r["unit"]) for r in rows):
        sub = [r for r in rows if r["subject"] == subject and r["unit"] == unit]
        independent = sum(r["outcome"] == "correct" for r in sub) / len(sub)
        first_sub = [r for r in first.values() if r["subject"] == subject and r["unit"] == unit]
        latest_sub = [r for r in latest.values() if r["subject"] == subject and r["unit"] == unit]
        out.append(f"  {subject}/{unit}: 演習 {len(sub)}回 / 異なる問題 {len(first_sub)}問, 演習回ごとの正答率 {accuracy(sub):.0%}"
                   f", 初回正答率 {accuracy(first_sub):.0%}, 最新正答率 {accuracy(latest_sub):.0%}"
                   f", 自力正答率 {independent:.0%}; レベル提案: {suggest_level(sub)}")
    out += ["", "※正答率はヒント使用を含む。初回・最新は科目/単元/問題IDごと。"
            "レベル提案は科目・単元ごとの直近10演習回（再演習を含む）。自動変更ではありません。"]
    return "\n".join(out)


def diagnose(rows: list[dict]) -> str:
    out = ["躓いた段（最初に落ちた段）:"]
    missing = sum(any(k not in r for k in ("teacher_eval", "self_eval", "stumble"))
                  or (r.get("stumble", "none") != "none" and "error_category" not in r)
                  for r in rows)
    out.insert(0, f"診断項目が不足した旧記録: {missing}問（未記録を問題なしとは扱わない）")
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
            for k in ("teacher-eval", "self-eval", "stumble"):
                p.add_argument(f"--{k}", required=True)
            p.add_argument("--error-category")
    a = ap.parse_args(argv)
    if a.cmd == "add":
        ap.exit(2, "ledger.py add は廃止しました。session.py start → finish で記録してください。\n")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print((report if a.cmd == "report" else diagnose)(load(a.ledger)))


if __name__ == "__main__":
    main()
