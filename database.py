"""SQLite paper trade storage."""
import os
import sqlite3
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "/data/trades.db" if os.path.isdir("/data") else "trades.db")


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                match_id TEXT,
                player1 TEXT,
                player2 TEXT,
                tournament TEXT,
                situation TEXT,
                leader TEXT,
                condition_id TEXT,
                token_id TEXT,
                event_slug TEXT,
                stat_prob REAL,
                ws_price REAL,
                verified_ask REAL,
                edge_ws REAL,
                edge_verified REAL,
                outcome TEXT DEFAULT 'pending',
                resolved_at TEXT,
                pnl REAL
            )
        """)
        conn.commit()
    print(f"[db] initialized at {DB_PATH}")


def record_trade(match_id, player1, player2, tournament, situation, leader,
                 condition_id, token_id, event_slug, stat_prob, ws_price, verified_ask) -> int:
    edge_ws = stat_prob - ws_price
    edge_verified = stat_prob - verified_ask if verified_ask is not None else None
    with _conn() as conn:
        cur = conn.execute("""
            INSERT INTO trades (created_at, match_id, player1, player2, tournament, situation,
                leader, condition_id, token_id, event_slug, stat_prob, ws_price, verified_ask,
                edge_ws, edge_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.now().isoformat(), str(match_id), player1, player2, tournament,
              situation, leader, condition_id, token_id, event_slug, stat_prob,
              ws_price, verified_ask, edge_ws, edge_verified))
        conn.commit()
        return cur.lastrowid


def resolve_trade(trade_id: int, outcome: str, pnl: float):
    with _conn() as conn:
        conn.execute("""
            UPDATE trades SET outcome=?, pnl=?, resolved_at=? WHERE id=?
        """, (outcome, pnl, datetime.now().isoformat(), trade_id))
        conn.commit()


def get_pending_trades() -> list[dict]:
    with _conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM trades WHERE outcome='pending' ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_trades(limit: int = 500) -> list[dict]:
    with _conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
