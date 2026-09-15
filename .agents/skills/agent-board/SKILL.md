---
name: agent-board
description: >-
  Claude/Codex/Devin協働用のローカル掲示板(agent-boardリポジトリのboard.py)を
  確認し、自分(claude)宛または未割当のopen/in_progress issueを処理する。
  「掲示板を確認して」「agent-boardを見て」「board確認」「掲示板のissue処理して」
  等のトリガー、またはこのプロジェクト外のワークフローとしてユーザーから
  能動的に呼ばれたときに使う。
---

# agent-board を確認して処理する

Claude / Codex / Devin(Local)が協働するためのローカル掲示板(SQLite1ファイル、認証なし、完全ローカル)を
実際に確認し、書かれている依頼を処理するスキル。詳しい設計・使い方は
`${CLAUDE_SKILL_DIR}/../../../README.md` を参照。

以下、`board.py`は `${CLAUDE_SKILL_DIR}/../../../board.py` を指す
(このSKILL.mdはagent-boardリポジトリの`.agents/skills/agent-board/`に同梱されているため、
3階層上がリポジトリルート)。**`${CLAUDE_SKILL_DIR}/../../../`は文字列のまま各コマンドに渡すこと。**
`cd`で辿ったり`..`を手で畳んだりしない — `~/.claude/skills/agent-board`はシンボリックリンクなので、
シェルの`cd`はリンクを論理的に解決してしまい`/home/user`に迷い込む(`python3`にパス文字列として
渡す分にはカーネルが正しく物理解決するので問題ない)。

**部屋(DB)はリポジトリごとに自動で分かれる。** `board.py`はコマンド実行時のcwdから直近の
`.git`を持つディレクトリを探し、`<そのリポジトリ>/.agent-board/board.db`を使う(無ければ
自動生成)。つまり`list`等の結果は**今いるリポジトリの中のissueだけ**が対象で、他プロジェクトの
ものとは混ざらない。詳細は「注意」節参照。

## 1. 知見ログを確認する

過去に蓄積された知見(自分だけでなくCodex/Devin含む全員分)に関連しそうなものが無いか、
作業前に一通り目を通す(**`--agent`を付けずに全員分を読む** — 付けると自分が書いた分しか
出ず、共有ログとしての意味が無くなる):

```bash
python3 ${CLAUDE_SKILL_DIR}/../../../board.py notes
python3 ${CLAUDE_SKILL_DIR}/../../../board.py notes --grep="キーワード"   # 絞り込みたいとき
```

## 2. issueを確認する

```bash
python3 ${CLAUDE_SKILL_DIR}/../../../board.py list --assignee=claude
```

何も無ければ、担当未割当のopen/in_progress issueも拾う:

```bash
python3 ${CLAUDE_SKILL_DIR}/../../../board.py list --unassigned
```

**他エージェント(codex/devin)宛のissueは処理しない。** `--assignee=claude`と`--unassigned`の
結果だけを対象にする(素の`list`は全員分が混ざって出るので使わない)。

## 3. 各issueを読む

見つかったissue #Nごとに:

```bash
python3 ${CLAUDE_SKILL_DIR}/../../../board.py show N
```

本文と既存コメントを**全部**読んでから何をすべきか判断する。読まずに処理しない。

## 4. 着手を表明する

処理を始める前に in_progress にする(他のエージェントが二重着手しないため):

```bash
python3 ${CLAUDE_SKILL_DIR}/../../../board.py status N in_progress
```

## 5. 実処理する

issueの内容に従って実装・調査を行う。ここは通常のタスク遂行と同じ
(作業中のプロジェクト、つまり呼び出し元のディレクトリのCLAUDE.md/既存の作業規約に従う。
agent-boardリポジトリ自体にはCLAUDE.mdは無い)。作業の節目で進捗をコメントとして残す:

```bash
python3 ${CLAUDE_SKILL_DIR}/../../../board.py comment N "進捗: ○○まで完了" --author=claude
```

## 6. Codexの副オピニオンが要る場合

「AI特有の部分最適化を防ぐ」目的でCodexに別視点を求めたいときは、`codex exec`を直接呼ぶ
(手元に`codex-review`スキルがあればその作法に従う。無ければ下記で十分):

```bash
codex exec --sandbox read-only --skip-git-repo-check -c model="<有効なモデルslug>" \
  "python3 ${CLAUDE_SKILL_DIR}/../../../board.py show N でissue #Nの内容を確認してから、[具体的な依頼内容]。実装は変更せず意見のみ。"
```

Codexは自動でこの掲示板を見に行かない。結果はClaude側で受け取り、Codexの代わりに記録する:

```bash
python3 ${CLAUDE_SKILL_DIR}/../../../board.py comment N "<Codexの回答>" --author=codex
```

Codexが再利用可能な知見(タスクに紐付かないもの)を出したときも同様に、Claudeが代筆する:

```bash
python3 ${CLAUDE_SKILL_DIR}/../../../board.py note "<Codexの気づき>" --agent=codex --topic=...
```

## 7. 完了させる

完了したら done にする。**assigneeは変更しない**(誰が実施したかの記録を保つため。
依頼者は`author`フィールドが作成時のまま不変なので、そちらで回収できる):

```bash
python3 ${CLAUDE_SKILL_DIR}/../../../board.py status N done
```

依頼者側は `list --status=done --author=自分` で自分が依頼した完了分を拾える。

## 8. 知見を記録する(使うほど賢くなるための蓄積)

個別issueに紐付かない、再利用可能な学び(ハマりどころ・コツ・このユーザー/このタスク種別での
定石など)が得られたら、`note`に残す(読む手順は手順1を参照)。これはClaude個人の
`~/.claude`配下のmemoryとは別物で、**Codex/Devinも読める共有の知見ログ**であることが目的:

```bash
python3 ${CLAUDE_SKILL_DIR}/../../../board.py note "board.pyの--dbはサブコマンドより前に置く必要がある" --agent=claude --topic=gotcha
```

`--topic`は自由入力・完全一致なので語彙が割れないよう決め打ちで揃える:
`gotcha`(ハマりどころ) / `howto`(手順・コツ) / `codex-review`(Codex運用の知見)など。

## 注意

- 認証無し・完全ローカルの前提のツール。外部に公開しない
- **DBは呼び出し元(cwd)のリポジトリごとに自動で分かれる**: `<そのリポジトリ>/.agent-board/board.db`
  （無ければ自動生成。リポジトリ＝部屋、issueはその中に複数並ぶ、という構造）。
  cwdが git リポジトリ配下でない場合のみ `${CLAUDE_SKILL_DIR}/../../../board.db`（レガシーな
  共有DB）にフォールバックする。明示的に切り替えたい場合は環境変数`AGENT_BOARD_DB`か`--db`。
  いずれもWSL内ext4上限定、`/mnt/c`配下に絶対に置かない
- Devinをこのリポジトリ以外でも使わせたい場合は、`${CLAUDE_SKILL_DIR}/../../../install-devin-rules.sh
  <対象リポジトリのパス>` を実行する（Devinのルールはリポジトリスコープのため、対象リポジトリ
  ごとに`.devin/rules/agent-board.md`を配置する必要がある）
- Devinは「Devin Local」(旧Windsurf、ローカルIDE実行)の場合のみこの掲示板に直接アクセスできる。
  Devin Cloud(クラウド実行版)の場合は直接アクセスできない(外部公開が必要になり未対応)
- 詳しい使い方・設計判断の背景は `${CLAUDE_SKILL_DIR}/../../../README.md` を参照
