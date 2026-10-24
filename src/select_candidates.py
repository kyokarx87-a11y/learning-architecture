#!/usr/bin/env python3
"""出題の候補を絞る。条件はここに持ち、AIにはこの出力だけを渡して「この中から選んで」と頼む。

規則: 未演習の問題を先に。無ければ、直近の記録で教師評価が△か×だった問題（復習）だけを候補にする。
問題の一覧（--pool）は1行1問題IDのテキスト。教材の本文は持たない。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ledger import load


def candidates(pool: list[str], rows: list[dict], unit: str, count: int) -> list[str]:
    done = {r["problem_id"] for r in rows}
    fresh = [p for p in pool if p not in done]
    if fresh:
        return fresh[:count]
    last = {}  # 問題IDごとの最新の記録（台帳は追記専用なので、後ろの行が新しい）
    for r in rows:
        if unit in r["unit"]:
            last[r["problem_id"]] = r
    review = [p for p, r in last.items() if r.get("teacher_eval") in ("△", "×")]
    return review[:count]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--pool", type=Path, required=True, help="問題IDの一覧（1行1件）")
    ap.add_argument("--unit", required=True)
    ap.add_argument("--count", type=int, default=5)
    a = ap.parse_args()
    pool = [l.strip() for l in a.pool.read_text(encoding="utf-8").splitlines() if l.strip()]
    for pid in candidates(pool, load(a.ledger), a.unit, a.count):
        print(pid)


if __name__ == "__main__":
    main()
