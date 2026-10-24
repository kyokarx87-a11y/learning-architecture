# AI家庭教師の実行契約

このリポジトリで演習するときは `docs/agent-workflow.md` と
`docs/practice-loop.md`、`docs/evaluation.md` を読んで従う。
開発・レビューの依頼では演習を始めず、必要なコードを確認してテストする。

- 出題は1問ずつ。生徒の回答を待ち、答えを先に見せない。
- 生徒の自己評価を推測・代入しない。返信を待つ。
- `src/session.py` の status → start →（必要なら hint）→ finish を使う。
  finish が成功するまで次の問題を出さない。エラーを状態削除で回避しない。
- 記録入口は `session.py finish` のみ。廃止済みの `ledger.py add` や、
  Python関数の直接呼出し・台帳の直接編集で演習の検査を迂回しない。
- 教材・個人記録は `local/` に置き、公開しない。出典・答えを検証できない問題を
  検証済みとして出さない。架空サンプルのIDだけでは問題文は取得できない。
- AIの採点や解説は誤り得る。疑義があれば確定せず、教材の解答や本人の確認に戻る。

検証: `python -m unittest discover -s tests`。
フックの自動配備や外部モデル呼出しは行わない。
