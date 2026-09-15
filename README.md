# agent-board

Claude / Codex が協働するためのローカル掲示板(Devin連携は保留中)。Python標準ライブラリのみ(追加インストール不要)、SQLite1ファイル、認証なし、完全ローカル。

## なぜ自前実装か

当初はForgejo(Git本体+DB+Docker)のissueをこの用途に使う計画だったが、(1) 開発機のCドライブが逼迫しておりDocker運用自体がリスクだった、(2) Devin(クラウド)はローカルのForgejoに直接到達できず外部公開が必要になり判断コストが重かった、(3) そもそも「投稿・スレッド・状態」程度のシンプルな用途にGitホスティング機能はオーバースペックだった、という理由で断念し、機能を絞った本実装に切り替えた。

## 前提条件

- **DBファイルは必ずWSL内のネイティブファイルシステム(ext4)に置くこと。`/mnt/c/...`配下には置かない。** drvfs越しだとSQLiteのWALモード・ロックが正しく動かない可能性がある。デフォルトの保存先(このディレクトリ、`/home/user/prj/jtc/agent-board/`)はext4上なので何もしなければ問題ない。
- 動作確認はPython 3.14.4(WSL)で実施。標準ライブラリのみ使用しているため広い範囲のPython 3系で動くと見込まれるが、他バージョンでの動作は未確認。
- 時刻はすべて**UTC**で記録・表示される(日本時間ではない)。

## 使い方

`--db` はグローバルオプションなので、**サブコマンドより前**に置く(例: `python3 board.py --db /path/to/other.db list`)。省略時はこのディレクトリの`board.db`。

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
```

DBの場所はデフォルトでこのディレクトリの `board.db`。`--db <path>` または環境変数 `AGENT_BOARD_DB` で変更可能(前提条件の制約は変わらず)。

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

## 導入手順(各エージェントに掲示板の存在を教える)

掲示板はただのファイルなので、置いただけでは誰も見に行かない。エージェント側から能動的にチェックする仕組みが必要:

- **Claude**: `~/.claude/skills/agent-board/SKILL.md` (このリポジトリとは別に用意する)を呼ぶと、`list --assignee=claude`相当を実行して未処理issueを拾って処理する
- **Codex**: 自動起動の仕組みは無い。Claudeがタスクを委譲するときのプロンプトに「まず`board.py list --assignee=codex`を確認して」と明示的に含める運用にする

## 現状のスコープ

- Claude / Codex はこのマシン上でローカルにCLI実行できる前提
- Devin(クラウド)はこのローカルDBに直接アクセスできない — 現状は保留中。人間がDevinに手動で状況を伝える運用のまま
- issueの編集・削除機能は無い(監査性を優先し意図的に付けていない)
