"""SQLite 数据持久化：存储余额快照，推算用量趋势。"""

import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Optional

DB_DIR = Path.home() / ".token-monitor"
DB_PATH = DB_DIR / "usage.db"


def _connect() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(c["name"] == column for c in cols)


def init_db() -> None:
    conn = _connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS balance_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            total_balance REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'CNY'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_usage (
            date TEXT PRIMARY KEY,
            estimated_cost REAL NOT NULL DEFAULT 0,
            last_balance REAL,
            update_count INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    # 迁移：如果缺少 last_drop 列则添加
    if not _column_exists(conn, "balance_snapshots", "last_drop"):
        conn.execute("ALTER TABLE balance_snapshots ADD COLUMN last_drop REAL DEFAULT 0")
    conn.commit()
    conn.close()


def record_snapshot(total_balance: float, currency: str = "CNY") -> float:
    """记录余额快照，返回本次与上次的差额（正值表示消费）。"""
    conn = _connect()
    now = datetime.now().isoformat()

    prev = conn.execute(
        "SELECT total_balance FROM balance_snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    drop = 0.0
    if prev is not None:
        delta = prev["total_balance"] - total_balance
        if delta > 0:
            drop = delta

    conn.execute(
        "INSERT INTO balance_snapshots (timestamp, total_balance, currency, last_drop) VALUES (?, ?, ?, ?)",
        (now, total_balance, currency, drop),
    )

    today = date.today().isoformat()
    prev = conn.execute(
        "SELECT last_balance FROM daily_usage WHERE date = ?", (today,)
    ).fetchone()

    if prev and prev["last_balance"] is not None:
        cost_delta = prev["last_balance"] - total_balance
        if cost_delta >= 0:
            conn.execute(
                "UPDATE daily_usage SET estimated_cost = estimated_cost + ?, last_balance = ?, update_count = update_count + 1 WHERE date = ?",
                (cost_delta, total_balance, today),
            )
    else:
        conn.execute(
            "INSERT OR REPLACE INTO daily_usage (date, estimated_cost, last_balance, update_count) VALUES (?, 0, ?, 1)",
            (today, total_balance),
        )

    conn.commit()
    conn.close()
    return drop


def get_last_drop() -> float:
    conn = _connect()
    row = conn.execute(
        "SELECT last_drop FROM balance_snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row["last_drop"] if row and row["last_drop"] else 0.0


def get_today_usage() -> dict:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM daily_usage WHERE date = ?",
        (date.today().isoformat(),),
    ).fetchone()
    conn.close()
    if row:
        return {
            "estimated_cost": row["estimated_cost"],
            "update_count": row["update_count"],
        }
    return {"estimated_cost": 0.0, "update_count": 0}


def get_month_usage() -> dict:
    conn = _connect()
    year_month = date.today().strftime("%Y-%m")
    rows = conn.execute(
        "SELECT SUM(estimated_cost) as total_cost, SUM(update_count) as total_updates FROM daily_usage WHERE date LIKE ?",
        (f"{year_month}%",),
    ).fetchone()
    conn.close()
    if rows and rows["total_cost"] is not None:
        return {"estimated_cost": rows["total_cost"], "update_count": rows["total_updates"] or 0}
    return {"estimated_cost": 0.0, "update_count": 0}


def get_last_balance() -> Optional[float]:
    conn = _connect()
    row = conn.execute(
        "SELECT total_balance FROM balance_snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row["total_balance"] if row else None


def get_history(days: int = 7) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM daily_usage ORDER BY date DESC LIMIT ?", (days,)
    ).fetchall()
    conn.close()
    return [
        {"date": r["date"], "estimated_cost": r["estimated_cost"], "update_count": r["update_count"]}
        for r in reversed(rows)
    ]


def clear_history() -> None:
    conn = _connect()
    conn.execute("DELETE FROM balance_snapshots")
    conn.execute("DELETE FROM daily_usage")
    conn.commit()
    conn.close()
