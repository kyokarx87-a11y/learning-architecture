# learning-architecture

**学習の設計（Learning Architecture）** — AIエージェントを家庭教師にして、数学・物理の問題演習を回すための
「ルール・記録・診断」の仕組みと、1問ずつ進める最小限のCLIハーネスです。
高校3年の受験勉強の中で作り、使いながら直してきた仕組みのうち、CLI部分を公開用の簡易版に整理しました。

> This is a simplified CLI showcase of part of a study system built around an AI tutor agent: a practice loop, a two-axis
> evaluation record (self vs. teacher), and a ledger that diagnoses *where* understanding stops.
> Sample data is fictional. Textbook content and personal records are intentionally excluded.

## 何を解決しようとしたか

| 困りごと | 仕組み |
|---|---|
| AIが答えをすぐ教えてしまい、自力で考える時間が減る | 出題→回答→ヒント（最大3回）→解答、の順を演習手順として定める（[docs/practice-loop.md](docs/practice-loop.md)） |
| 「できたつもり」と実際のズレに気づけない | 自己評価と教師評価を別々に記録し、ずれを診断に使う（[docs/evaluation.md](docs/evaluation.md)） |
| 正解／不正解だけでは弱点が分からない | 「どの段で躓いたか」「誤答の種類」を台帳に残して集計する |
| AIが決めたルールを守らなくなる | 共通CLIで開始した問題の未記録・評価矛盾を検出する（[docs/design-principles.md](docs/design-principles.md)）。CLIの検査対象は開始・ヒント・終了の手順と評価の入力の整合性です |

## 中身

```
docs/    仕組みの説明（演習ループ・評価・設計の原則）
src/     演習状態（session.py）／台帳と診断（ledger.py）／候補選定（select_candidates.py）
data/    架空のサンプル台帳
tests/   動作確認（unittest）
```

## 動かしてみる

Python 3.9 以上が必要です（標準ライブラリのみ）。

```bash
python src/ledger.py report --ledger data/sample_ledger.jsonl
python src/ledger.py diagnose --ledger data/sample_ledger.jsonl
python src/select_candidates.py --ledger data/sample_ledger.jsonl --pool data/sample_pool.txt --subject math --unit 数列 --count 3
python -m unittest discover -s tests
```

記録は演習の開始から1問ずつ行います。科目・単元専用の問題ID一覧を用意し、
出題・解答・自己評価待ちを含む[演習手順](docs/agent-workflow.md)に従ってください。

```bash
python src/session.py start --pool local/pool.txt --subject math --unit 数列
```

`ledger.py add`は廃止しました。進行中のヒント数を知らずに記録できる経路をなくすため、
公式CLIの追記入口は`session.py finish`だけです。既存台帳のreport / diagnoseは引き続き使えます。

## 含めていないもの

- 教材（問題集・参考書・過去問）の本文や図：著作権があるため含めません。
- 実際の学習記録・個人情報・認証情報。サンプルはすべて架空です。
- 本番運用の問題データベース、専用フック、複数PC同期は含めません。

## Claude Code / Codexで使う

このフォルダを開き、[AIとの演習手順](docs/agent-workflow.md)に従って始めてください。
[AGENTS.md](AGENTS.md)と[CLAUDE.md](CLAUDE.md)が共通手順への入口です。
問題文・確認用の解答と、科目・単元専用の問題ID一覧を自分で用意します。
サンプルIDはCLIの動作確認用です。問題文と解答は利用者が用意します。

`session.py`は、未記録の問題がある間の次の出題開始、4回目のヒント、
自己評価などの不足した記録、ヒント数・正誤・教師評価・躓きの矛盾を拒否します。
記録はGit追跡外の`local/`に置きます。
AIは共通の演習手順に従ってCLIを呼びます。このCLIは、開始・ヒント・終了の手順と、評価の入力の整合性を検査します。解答の採点と内容の確認は、人が行います。

## いまの範囲と今後の予定

自己評価と教師評価の分離、上流の躓きの記録、即時保存は、このハーネスの中核です。
公開データは、動作を示すための架空のサンプルです。
現在のレベル変更は科目・単元ごとの**提案**です。
今後の拡張として、復習日程の自動計算、自動昇段、難度データとの連携、時間の記録を予定しています。
学習効果の確認方法として、ヒントなしの自力正答率、日を空けた再演習、未見問題での確認を想定しています。
reportは演習回数と異なる問題数、問題別の初回正答率と最新正答率を分けて表示します。
コードを評価して改善した内容は[公開版の評価記録](docs/harness-review.md)にまとめています。

## ライセンス

MIT（[LICENSE](LICENSE)）
