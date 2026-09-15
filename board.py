#!/usr/bin/env python3
"""agent-board: Claude / Codex が使うローカル掲示板(Devin連携は保留中)。標準ライブラリのみ、認証なし。"""
import argparse
import html
import os
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_DB = Path(os.environ.get("AGENT_BOARD_DB", Path(__file__).parent / "board.db"))
STATUSES = ("open", "in_progress", "done")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            author TEXT NOT NULL,
            assignee TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER NOT NULL REFERENCES issues(id),
            author TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    conn.row_factory = sqlite3.Row
    return conn


def cmd_new(args, conn):
    body = args.body or ""
    if body == "-":
        body = sys.stdin.read()
    ts = now()
    cur = conn.execute(
        "INSERT INTO issues (title, body, status, author, assignee, created_at, updated_at) "
        "VALUES (?, ?, 'open', ?, ?, ?, ?)",
        (args.title, body, args.author, args.assignee, ts, ts),
    )
    conn.commit()
    print(f"#{cur.lastrowid} created")


def cmd_list(args, conn):
    params = []
    if args.status == "all":
        query = "SELECT * FROM issues"
    else:
        statuses = [s for s in args.status.split(",") if s]
        unknown = [s for s in statuses if s not in STATUSES]
        if unknown:
            print(f"不明なstatus: {','.join(unknown)} (使えるのは {','.join(STATUSES)},all)", file=sys.stderr)
            sys.exit(1)
        placeholders = ",".join("?" * len(statuses))
        params.extend(statuses)
        query = f"SELECT * FROM issues WHERE status IN ({placeholders})"
    if args.assignee:
        query += (" AND" if params else " WHERE") + " assignee = ?"
        params.append(args.assignee)
    if args.author:
        query += (" AND" if params else " WHERE") + " author = ?"
        params.append(args.author)
    query += " ORDER BY status, updated_at DESC, id" if args.status == "all" else " ORDER BY updated_at DESC, id"
    rows = conn.execute(query, params).fetchall()
    if not rows:
        print("(該当issueなし)")
        return
    for r in rows:
        assignee = f" -> {r['assignee']}" if r["assignee"] else ""
        print(f"#{r['id']:<4} [{r['status']:<11}] {r['title']}{assignee}  (by {r['author']}, {r['updated_at']})")


def cmd_show(args, conn):
    r = conn.execute("SELECT * FROM issues WHERE id = ?", (args.id,)).fetchone()
    if not r:
        print(f"#{args.id} は存在しません", file=sys.stderr)
        sys.exit(1)
    print(f"#{r['id']} {r['title']}")
    print(f"status: {r['status']}  author: {r['author']}  assignee: {r['assignee'] or '-'}")
    print(f"created: {r['created_at']}  updated: {r['updated_at']}")
    print("---")
    print(r["body"])
    comments = conn.execute(
        "SELECT * FROM comments WHERE issue_id = ? ORDER BY created_at, id", (args.id,)
    ).fetchall()
    if comments:
        print("\n--- comments ---")
        for c in comments:
            print(f"[{c['created_at']}] {c['author']}: {c['body']}")


def cmd_comment(args, conn):
    r = conn.execute("SELECT id FROM issues WHERE id = ?", (args.id,)).fetchone()
    if not r:
        print(f"#{args.id} は存在しません", file=sys.stderr)
        sys.exit(1)
    body = sys.stdin.read() if args.body == "-" else args.body
    ts = now()
    conn.execute(
        "INSERT INTO comments (issue_id, author, body, created_at) VALUES (?, ?, ?, ?)",
        (args.id, args.author, body, ts),
    )
    conn.execute("UPDATE issues SET updated_at = ? WHERE id = ?", (ts, args.id))
    conn.commit()
    print(f"#{args.id} にコメント追加")


def cmd_status(args, conn):
    r = conn.execute("SELECT id FROM issues WHERE id = ?", (args.id,)).fetchone()
    if not r:
        print(f"#{args.id} は存在しません", file=sys.stderr)
        sys.exit(1)
    if args.assignee is not None:
        conn.execute(
            "UPDATE issues SET status = ?, assignee = ?, updated_at = ? WHERE id = ?",
            (args.new_status, args.assignee, now(), args.id),
        )
    else:
        conn.execute(
            "UPDATE issues SET status = ?, updated_at = ? WHERE id = ?", (args.new_status, now(), args.id)
        )
    conn.commit()
    assignee_note = f" (assignee -> {args.assignee})" if args.assignee is not None else ""
    print(f"#{args.id} -> {args.new_status}{assignee_note}")


def render_html(conn) -> str:
    rows = conn.execute("SELECT * FROM issues ORDER BY status, updated_at DESC, id").fetchall()
    parts = [
        "<title>Agent Board</title>",
        "<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem}",
        "table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:.5rem;text-align:left;vertical-align:top}",
        ".open{color:#b00}.in_progress{color:#a60}.done{color:#0a0}",
        "pre{white-space:pre-wrap;background:#f6f6f6;padding:.5rem;border-radius:4px}</style>",
        "<h1>Agent Board</h1>",
        "<table><tr><th>#</th><th>status</th><th>title</th><th>assignee</th><th>author</th><th>updated</th></tr>",
    ]
    for r in rows:
        parts.append(
            f"<tr><td>{r['id']}</td><td class='{r['status']}'>{r['status']}</td>"
            f"<td>{html.escape(r['title'])}</td><td>{html.escape(r['assignee'] or '')}</td>"
            f"<td>{html.escape(r['author'])}</td><td>{r['updated_at']}</td></tr>"
        )
    parts.append("</table>")
    for r in rows:
        parts.append(f"<h3 id='issue-{r['id']}'>#{r['id']} {html.escape(r['title'])}</h3>")
        parts.append(f"<pre>{html.escape(r['body'])}</pre>")
        comments = conn.execute(
            "SELECT * FROM comments WHERE issue_id = ? ORDER BY created_at, id", (r["id"],)
        ).fetchall()
        for c in comments:
            parts.append(f"<p><b>{html.escape(c['author'])}</b> ({c['created_at']}): {html.escape(c['body'])}</p>")
    return "\n".join(parts)


def read_connect(db_path: Path) -> sqlite3.Connection:
    """serve用: DDL/PRAGMAを毎回打たない軽量接続（新規スレッドごとに1本開く）。"""
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def cmd_serve(args, conn):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            with closing(read_connect(args.db)) as c:
                body = render_html(c).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *a):
            pass

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"http://{args.host}:{args.port} で読み取り専用ビューを公開中 (Ctrl+C で終了)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("new", help="issueを作成")
    sp.add_argument("title")
    sp.add_argument("--body", default=None, help="'-' を指定すると標準入力から読む。省略時は空")
    sp.add_argument("--author", required=True)
    sp.add_argument("--assignee", default=None)
    sp.set_defaults(func=cmd_new)

    sp = sub.add_parser("list", help="issue一覧")
    sp.add_argument("--status", default="open,in_progress", help=f"カンマ区切り or all ({','.join(STATUSES)})")
    sp.add_argument("--assignee", default=None, help="現在の担当で絞り込み")
    sp.add_argument("--author", default=None, help="依頼者(作成時のまま不変)で絞り込み。完了分の回収に使う")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("show", help="issue詳細+コメント表示")
    sp.add_argument("id", type=int)
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("comment", help="コメント追加")
    sp.add_argument("id", type=int)
    sp.add_argument("body", help="'-' を指定すると標準入力から読む")
    sp.add_argument("--author", required=True)
    sp.set_defaults(func=cmd_comment)

    sp = sub.add_parser("status", help="ステータス変更")
    sp.add_argument("id", type=int)
    sp.add_argument("new_status", choices=STATUSES)
    sp.add_argument("--assignee", default=None, help="同時に担当を付け替える(例: 完了時に依頼者へ戻す)")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("serve", help="読み取り専用HTMLビューを起動")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8765)
    sp.set_defaults(func=cmd_serve)

    args = p.parse_args()
    conn = connect(args.db)
    args.func(args, conn)


if __name__ == "__main__":
    main()
