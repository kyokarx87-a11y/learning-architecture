#!/usr/bin/env python3
"""1問ずつの演習状態。単一プロセスで使うローカルCLI（外部API・フック不要）。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from ledger import append, load, make_record
from select_candidates import candidates


def read_state(path: Path) -> dict:
    if not path.exists():
        return {}
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise ValueError("状態ファイルが不正です")
    if state:
        for key in ("attempt_id", "subject", "unit", "problem_id", "ledger"):
            if not isinstance(state.get(key), str) or not state[key].strip():
                raise ValueError(f"状態ファイルの {key} が不正です")
        if type(state.get("hints")) is not int or not 0 <= state["hints"] <= 3:
            raise ValueError("状態ファイルの hints が不正です")
    return state


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def recover(path: Path, state: dict) -> dict:
    """台帳追記後に中断した場合、同じ attempt_id を二重に追記しない。"""
    if state:
        ledger = Path(state["ledger"])
        if ledger.exists() and any(r.get("attempt_id") == state["attempt_id"] for r in load(ledger)):
            write_state(path, {})
            return {}
    return state


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", type=Path, default=Path("local/session.json"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    start = sub.add_parser("start")
    start.add_argument("--ledger", type=Path, default=Path("local/ledger.jsonl"))
    start.add_argument("--pool", type=Path, required=True)
    start.add_argument("--subject", required=True)
    start.add_argument("--unit", required=True)
    sub.add_parser("hint")
    finish = sub.add_parser("finish")
    for key in ("outcome", "teacher-eval", "self-eval", "stumble"):
        finish.add_argument(f"--{key}", required=True)
    finish.add_argument("--error-category")
    a = ap.parse_args(argv)
    try:
        state = recover(a.state, read_state(a.state))
        if a.cmd == "status":
            print(json.dumps(state or {"status": "ready"}, ensure_ascii=False))
        elif a.cmd == "start":
            if state:
                raise ValueError("未記録の問題があります。自己評価を受け取り finish してから次へ進んでください")
            paths = (a.state.resolve(), a.ledger.resolve(), a.pool.resolve())
            if len(set(paths)) != 3 or a.state.with_suffix(a.state.suffix + ".tmp").resolve() in paths[1:]:
                raise ValueError("状態・台帳・問題プールは別ファイルにしてください")
            rows = load(a.ledger) if a.ledger.exists() else []
            pool = [s.strip() for s in a.pool.read_text(encoding="utf-8").splitlines() if s.strip()]
            selected = candidates(pool, rows, a.unit, 1, a.subject)
            if not selected:
                raise ValueError("候補なし。単元専用プールを見直すか、復習範囲を本人と相談してください")
            state = {"attempt_id": str(uuid4()), "subject": a.subject, "unit": a.unit,
                     "problem_id": selected[0], "ledger": str(a.ledger.resolve()), "hints": 0}
            if not a.subject.strip() or not a.unit.strip():
                raise ValueError("科目・単元は空にできません")
            write_state(a.state, state)
            print(json.dumps(state, ensure_ascii=False))
        else:
            if not state:
                raise ValueError("進行中の問題がありません。start してください")
            if a.cmd == "hint":
                if state["hints"] >= 3:
                    raise ValueError("ヒントは3回までです。「解答です。」と宣言して解説してください")
                state["hints"] += 1
                write_state(a.state, state)
                print(f"ヒント {state['hints']}/3")
            else:
                if a.outcome == "correct" and state["hints"]:
                    raise ValueError("ヒント使用後は correct を記録できません")
                if a.outcome == "correctWithHints" and not state["hints"]:
                    raise ValueError("correctWithHints には hint の記録が必要です")
                for key in ("subject", "unit", "problem_id"):
                    setattr(a, key, state[key])
                rec = make_record(a, hints=state["hints"])
                rec.update(attempt_id=state["attempt_id"], hints=state["hints"])
                append(Path(state["ledger"]), rec)
                write_state(a.state, {})
                print("記録済み。次の問題へ進めます")
    except (OSError, ValueError) as exc:
        ap.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
