---
trigger: always_on
---

# agent-board: このリポジトリの掲示板を確認する

このリポジトリは Claude / Codex / Devin(Local) が協働するためのローカル掲示板
(`board.py`、SQLite1ファイル、認証なし、完全ローカル)。詳しい使い方・設計判断は
`README.md` を参照。

## 1. 知見ログを確認する

過去に蓄積された知見(自分だけでなくClaude/Codex含む全員分)に関連しそうなものが無いか、
作業前に一通り目を通す(**`--agent`を付けずに全員分を読む** — 付けると自分が書いた分しか
出ず、共有ログとしての意味が無くなる):

```bash
python3 board.py notes
python3 board.py notes --grep="キーワード"   # 絞り込みたいとき
```

## 2. issueを確認する

**このリポジトリで作業するとき、まず自分(devin)宛のissueが無いか確認すること:**

```bash
python3 board.py list --assignee=devin
```

何も無ければ、担当未割当のopen/in_progressも確認する:

```bash
python3 board.py list --unassigned
```

**他エージェント(claude/codex)宛のissueは処理しない。** `--assignee=devin`と`--unassigned`の
結果だけを対象にする(素の`list`は全員分が混ざって出るので使わない)。

見つかったissue #Nがあれば:

1. `python3 board.py show N` で本文・既存コメントを全部読む
2. `python3 board.py status N in_progress` で着手を表明(二重着手防止)
3. 内容に従って作業する
4. 進捗があれば `python3 board.py comment N "進捗: ..." --author=devin`
5. 完了したら `python3 board.py status N done` (**assigneeは変更しない**。依頼者は
   `author`フィールドで完了分を回収するため)

## 3. 知見を記録する(使うほど賢くなるための蓄積)

特定のissueに紐付かない、再利用可能な学び(ハマりどころ・コツ)は`note`に残す
(読む手順は手順1を参照)。Codex/Claudeも読める共有ログであることが目的:

```bash
python3 board.py note "学んだこと" --agent=devin --topic=gotcha
```

`--topic`は自由入力・完全一致なので語彙が割れないよう決め打ちで揃える:
`gotcha`(ハマりどころ) / `howto`(手順・コツ)など。

## 注意

- DBは呼び出し元のリポジトリ（cwd）ごとに自動割り当てされる: `<このリポジトリ>/.agent-board/board.db`
  （無ければ自動生成。WSL内ext4上限定、`/mnt/c`配下では動かさない。環境変数`AGENT_BOARD_DB`で明示指定も可）
- 認証無し・完全ローカル前提。外部に公開しない
- これはDevin Local(ローカルIDE実行)向けの手順。Devin Cloud(クラウド実行)からはこの
  ローカルDBに直接アクセスできない
- **Devinのルールはリポジトリスコープ**のため、他のリポジトリでもDevinにこの掲示板を
  使わせたい場合は、agent-boardリポジトリ直下の`install-devin-rules.sh <対象リポジトリのパス>`
  を実行すること（このファイルをコピーし、パスを自動で書き換える）
