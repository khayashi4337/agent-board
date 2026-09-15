#!/usr/bin/env bash
# agent-boardのDevin向けルールファイルを、指定した別リポジトリへ導入する。
# Devinのルールはリポジトリスコープ(.devin/rules/)なので、使わせたいリポジトリ
# それぞれにコピーする必要がある。このスクリプトはそのコピー+パス書き換えを自動化する。
#
# 使い方: ./install-devin-rules.sh <対象リポジトリのパス>
set -euo pipefail

AGENT_BOARD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$AGENT_BOARD_ROOT/.devin/rules/agent-board.md"

if [ $# -ne 1 ]; then
  echo "使い方: $0 <対象リポジトリのパス>" >&2
  exit 1
fi

TARGET_REPO="$(cd "$1" && pwd)"
if [ ! -d "$TARGET_REPO/.git" ]; then
  echo "エラー: $TARGET_REPO は.gitが無く、gitリポジトリに見えません" >&2
  exit 1
fi

DEST_DIR="$TARGET_REPO/.devin/rules"
DEST="$DEST_DIR/agent-board.md"
mkdir -p "$DEST_DIR"

# python3 board.py -> python3 <絶対パス>/board.py に書き換えつつコピー
sed \
  -e "s|python3 board\.py|python3 $AGENT_BOARD_ROOT/board.py|g" \
  -e '/^## 注意$/,$ { /^- 認証無し/i\
- このファイルは '"$AGENT_BOARD_ROOT"'/install-devin-rules.sh により自動生成された。\
  元ファイル( '"$AGENT_BOARD_ROOT"'/.devin/rules/agent-board.md )を更新した場合は\
  同スクリプトを再実行して同期すること。
}' \
  "$SRC" > "$DEST"

echo "導入完了: $DEST"
echo "(このリポジトリの .agent-board/ ディレクトリを .gitignore に追加することを推奨)"
