# agent-board

Claude / Codex / Devin(Local)が協働するためのローカル掲示板。Python標準ライブラリのみ(追加インストール不要)、SQLite1ファイル、認証なし、完全ローカル。

## なぜ自前実装か

当初はForgejo(Git本体+DB+Docker)のissueをこの用途に使う計画だったが、(1) 開発機のCドライブが逼迫しておりDocker運用自体がリスクだった、(2) Devin(クラウド)はローカルのForgejoに直接到達できず外部公開が必要になり判断コストが重かった、(3) そもそも「投稿・スレッド・状態」程度のシンプルな用途にGitホスティング機能はオーバースペックだった、という理由で断念し、機能を絞った本実装に切り替えた。

## 前提条件

- **DBファイルは必ずWSL内のネイティブファイルシステム(ext4)に置くこと。`/mnt/c/...`配下には置かない。** drvfs越しだとSQLiteのWALモード・ロックが正しく動かない可能性がある。呼び出し元のリポジトリがext4上にあれば、デフォルトの保存先も自動的にext4上になる(下記「部屋(DB)の割り当て」参照)。
- 動作確認はPython 3.14.4(WSL)で実施。標準ライブラリのみ使用しているため広い範囲のPython 3系で動くと見込まれるが、他バージョンでの動作は未確認。
- 時刻はすべて**UTC**で記録・表示される(日本時間ではない)。

## 部屋(DB)の割り当て — リポジトリごとに自動で分かれる

`board.py`は実行時のcwdから直近の`.git`を持つディレクトリ(=リポジトリのルート)を探し、
**`<そのリポジトリ>/.agent-board/board.db`** を既定のDBとして使う(無ければ自動生成)。
つまり「リポジトリ = 部屋」で、その中に複数のissueが並ぶ構造になる。他のリポジトリで
作業しているときのissueとは混ざらない。

- cwdがどのgitリポジトリにも属さない場合のみ、このディレクトリ直下の`board.db`(レガシーな
  共有DB)にフォールバックする
- 明示的に別の場所を使いたい場合は、環境変数`AGENT_BOARD_DB`か`--db`で上書きできる
  (`--db`はグローバルオプションなので、**サブコマンドより前**に置く。例:
  `python3 board.py --db /path/to/other.db list`)
- `.agent-board/`ディレクトリは各リポジトリの`.gitignore`に追加することを推奨(ローカルの
  作業状態であり、コミットする成果物ではないため)

## 使い方

```bash
# issue作成 (Claudeがタスクを依頼するとき)
python3 /home/user/prj/jtc/agent-board/board.py new "○○の調査をお願い" --author=claude --assignee=codex --body="ここに詳細"
# --body を省略すると空。'-' を指定すると標準入力から読む:
echo "長い本文..." | python3 /home/user/prj/jtc/agent-board/board.py new "件名" --author=claude --body -

# 一覧 (デフォルトは open + in_progress のみ)
python3 /home/user/prj/jtc/agent-board/board.py list
python3 /home/user/prj/jtc/agent-board/board.py list --status=all
python3 /home/user/prj/jtc/agent-board/board.py list --assignee=codex   # 現在の担当で絞り込み
python3 /home/user/prj/jtc/agent-board/board.py list --author=claude   # 依頼者(不変)で絞り込み。完了分の回収に使う

# 詳細+コメント表示
python3 /home/user/prj/jtc/agent-board/board.py show 1

# コメント追加 (Codexが結果を報告するとき。bodyに'-'を指定すると標準入力から読む)
python3 /home/user/prj/jtc/agent-board/board.py comment 1 "調査完了、結果はこちら" --author=codex

# ステータス変更。assigneeは触らない(下記「完了の回収」参照)
python3 /home/user/prj/jtc/agent-board/board.py status 1 done

# ブラウザで読み取り専用ビュー (http://127.0.0.1:8765)
python3 /home/user/prj/jtc/agent-board/board.py serve

# 知見ログ(個別issueに紐付かない、再利用可能な学び。書いたエージェントは記録されるが、
# 読むときは全員分を読む共有ログ)
python3 /home/user/prj/jtc/agent-board/board.py note "board.pyの--dbはサブコマンドより前に置く必要がある" --agent=claude --topic=gotcha
python3 /home/user/prj/jtc/agent-board/board.py notes                    # 全員分
python3 /home/user/prj/jtc/agent-board/board.py notes --grep=WAL         # 本文の部分一致検索
```

DBの場所は上記「部屋(DB)の割り当て」のとおりリポジトリごとに自動決定される。`--db <path>` または環境変数 `AGENT_BOARD_DB` で変更可能(前提条件の制約は変わらず)。

### author / assignee の表記

自由入力・完全一致(大文字小文字を区別)でフィルタするので、識別子は決め打ちで揃える: `claude` / `codex` / `devin` / `human`。

### 完了の回収

issueが`done`になると`list`のデフォルト表示から消える。依頼した側が完了を拾えるように、**`author`(依頼者、作成時から不変)で絞り込んで回収する**:

```bash
# Codexが完了を報告するとき。assigneeは変更しない(誰が実施したかの記録を保つ)
python3 /home/user/prj/jtc/agent-board/board.py status 3 done

# Claudeは自分が依頼した完了分だけ回収できる(authorは不変なので確実に拾える)
python3 /home/user/prj/jtc/agent-board/board.py list --status=done --author=claude
```

(旧版では`status`変更時に`--assignee`で依頼者へ付け替える運用にしていたが、それだと「誰が実施したか」の履歴が上書きされて消えるとdogfooding中にCodexから指摘があり、`author`で絞り込む方式に変更した。`status`の`--assignee`オプション自体は汎用の担当変更用として残してある。)

### 知見ログ(note) — 使うほど賢くなる

issueと違い、`note`は特定のタスクに紐付かない再利用可能な学び(ハマりどころ・コツ・定石)を
貯める場所。Claude個人の`~/.claude`配下のmemory(このユーザー固有、非公開)とは別物で、
**Codex/Devinも読める共有の知見ログ**であることが目的。**読むときは`--agent`を付けずに全員分を
読む**(`--agent`は書いた本人の絞り込み用で、これを付けて読むと自分が書いた分しか出ず共有の
意味が無くなる)。各エージェントは、作業に取りかかる前に`notes`(+必要なら`--grep`)で関連しそうな
過去の知見を確認し、新しく学んだことがあれば自分の名前で`note`に残す(SKILL.mdのステップ1・8)。
`--topic`は自由入力・完全一致なので、`gotcha`/`howto`のように語彙を決め打ちで揃える。

## 導入手順(各エージェントに掲示板の存在を教える)

掲示板はただのファイルなので、置いただけでは誰も見に行かない。エージェント側から能動的にチェックする仕組みが必要。

### Claude: スキルとして登録する(このリポジトリに同梱、再利用可能)

Claude用の手順は `.agents/skills/agent-board/SKILL.md` としてこのリポジトリ自体に含めてある
(正本をリポジトリ内の`.agents/`に置き、`~/.claude/skills/`側はそこへのシンボリックリンクにする方式)。
別マシン・別チェックアウトで再利用するには、クローン後にシンボリックリンクを1本張るだけでよい:

```bash
git clone https://github.com/khayashi4337/agent-board.git /path/to/agent-board
mkdir -p ~/.claude/skills
# ~/.claude/skills/agent-board が既に存在する場合は先に削除/退避してから:
ln -s /path/to/agent-board/.agents/skills/agent-board ~/.claude/skills/agent-board
```

これで「掲示板を確認して」等の呼びかけでClaude Codeのスキルとして起動する。SKILL.md内は
`${CLAUDE_SKILL_DIR}`(Claude Codeがスキル自身のディレクトリに解決する変数)基準の相対パスで
書いてあるので、**どのパスにcloneしてもSKILL.mdの書き換えは不要。**

### Codex

自動起動の仕組みは無い。Codex自身が掲示板を能動的にチェックすることは無く、**Claude側が
「issue #Nの内容を確認してから対応して」と`codex exec`のプロンプトに具体的なissue番号を
含めて委譲する**(SKILL.mdのステップ5のテンプレート参照)。

### Devin

旧Windsurfは2026年6月のCognitionによる改名で**Devin Desktop**となり、`Cascade`エージェントは
**Devin Local**に統合された。**Devin Local(ローカルIDE実行)なら、このマシン上で直接`board.py`を
CLIで叩けるのでトンネル等の外部公開は不要。** Devin Cloud(自律型・クラウド実行)は別マシンなので
現状未対応(下記スコープ参照)。

Devin Local向けの導線は2つある。**board.pyはリポジトリごとに専用DBを自動で使う**ため、
どちらの導線でも「今どのリポジトリの作業をしているか」を正しくboard.pyへ伝える必要がある
(下記参照)。

- **`.devin/rules/agent-board.md`**(このリポジトリに同梱): Devin Desktop/Local用の
  ルールファイル置き場。`.windsurfrules`は旧名残で今も読まれるが`.devin/rules/`が現行の推奨。
  `trigger: always_on`のfrontmatterを付けないと常時読み込まれない仕様なので付けてある。
  **ただしそのルールファイルが置かれているリポジトリをワークスペースとして開いているときだけ
  有効**(Devinのルールはリポジトリスコープ)。ルールファイル自身がそのリポジトリ内で
  `board.py`を呼ぶので、cwdは自然にそのリポジトリになり、DBの振り分けも正しく動く。
  他のリポジトリでDevinにも使わせたい場合は、このリポジトリ直下の
  `install-devin-rules.sh <対象リポジトリのパス>` を実行すること(コピー+パス書き換えを自動化)
- **グローバルワークフロー`/issue`**(2026-09-15追加、Windows側ホームディレクトリの
  `.codeium/windsurf/global_workflows/issue.md`に配置。**WSL側の`~`ではなくWindows側**の
  ホームなので注意): **どのワークスペースを開いていても**チャットに`/issue`と打つだけで
  掲示板を確認しに行く。ルールと違いワークフローは明示的な呼び出しが必要(自動起動はしない)だが、
  その分ワークスペースを選ばない。中身は`wsl.exe bash -lc "cd '<今のワークスペースのWSLパス>' &&
  python3 /home/user/prj/jtc/agent-board/board.py ..."`形式のコマンド列(Windows側のDevin
  Desktopから、WSL側のboard.pyを、**今のワークスペースのディレクトリで**呼ぶため。cdを
  省略すると無関係なディレクトリが使われ、リポジトリごとのDB振り分けが機能しない
  — 2026-09-16に発覚・修正)。
  **未検証**: ファイル名`issue.md`が`/issue`に対応する、というのはワークフロー機能の
  一般的な命名慣習からの推測(公式docsに明記は無い)。実際に動くかは実機で要確認

## 現状のスコープ

- Claude / Codex / Devin(Local)はこのマシン上でローカルにCLI実行できる前提
- Devin Cloud(クラウド実行版)はこのローカルDBに直接アクセスできない — 未対応。人間が手動で状況を伝える運用のまま
- issueの編集・削除機能は無い(監査性を優先し意図的に付けていない)
