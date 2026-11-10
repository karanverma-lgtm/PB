"""Database management module for StockMightyBot alerts and watchlists."""

import sqlite3
import os
from typing import List, Dict, Any, Optional

DB_FILE = os.path.join(os.path.dirname(__file__), "alerts.db")


def get_db_connection() -> sqlite3.Connection:
    """Return a database connection with dictionary-like row factory."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize SQLite tables for alerts and watchlists."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                target_price REAL NOT NULL,
                condition TEXT NOT NULL, -- 'ABOVE' or 'BELOW'
                initial_price REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                triggered_at TIMESTAMP NULL,
                trigger_price REAL NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, symbol)
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts (is_active)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts (user_id, is_active)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist (user_id)"
        )
        conn.commit()


# ---------------------------------------------------------
# Alerts Methods
# ---------------------------------------------------------

def add_alert(
    user_id: int,
    chat_id: int,
    symbol: str,
    target_price: float,
    condition: str,
    initial_price: float,
    currency: str = "USD",
) -> int:
    """Add a new price alert to the database."""
    symbol = symbol.strip().upper()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO alerts (user_id, chat_id, symbol, target_price, condition, initial_price, currency, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (user_id, chat_id, symbol, target_price, condition, initial_price, currency),
        )
        conn.commit()
        return cursor.lastrowid


def get_user_alerts(user_id: int) -> List[Dict[str, Any]]:
    """Retrieve all active alerts for a specific user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, chat_id, symbol, target_price, condition, initial_price, currency, created_at
            FROM alerts
            WHERE user_id = ? AND is_active = 1
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_all_active_alerts() -> List[Dict[str, Any]]:
    """Retrieve all active alerts across all users for background checking."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, chat_id, symbol, target_price, condition, initial_price, currency
            FROM alerts
            WHERE is_active = 1
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def delete_alert(alert_id: int, user_id: Optional[int] = None) -> bool:
    """Delete (deactivate) an alert by ID, optionally verifying ownership."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if user_id is not None:
            cursor.execute(
                "UPDATE alerts SET is_active = 0 WHERE id = ? AND user_id = ?",
                (alert_id, user_id),
            )
        else:
            cursor.execute(
                "UPDATE alerts SET is_active = 0 WHERE id = ?",
                (alert_id,),
            )
        conn.commit()
        return cursor.rowcount > 0


def clear_user_alerts(user_id: int) -> int:
    """Clear all active alerts for a user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE alerts SET is_active = 0 WHERE user_id = ? AND is_active = 1",
            (user_id,),
        )
        conn.commit()
        return cursor.rowcount


def mark_alert_triggered(alert_id: int, trigger_price: float) -> None:
    """Mark an alert as triggered so it won't fire repeatedly."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE alerts
            SET is_active = 0,
                triggered_at = CURRENT_TIMESTAMP,
                trigger_price = ?
            WHERE id = ?
            """,
            (trigger_price, alert_id),
        )
        conn.commit()


# ---------------------------------------------------------
# Watchlist Methods
# ---------------------------------------------------------

def add_to_watchlist(user_id: int, symbol: str) -> bool:
    """Add a symbol to user's watchlist."""
    symbol = symbol.strip().upper()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO watchlist (user_id, symbol) VALUES (?, ?)",
                (user_id, symbol),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Already in watchlist


def get_user_watchlist(user_id: int) -> List[str]:
    """Get all symbols in user's watchlist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT symbol FROM watchlist WHERE user_id = ? ORDER BY created_at ASC",
            (user_id,),
        )
        return [row["symbol"] for row in cursor.fetchall()]


def remove_from_watchlist(user_id: int, symbol: str) -> bool:
    """Remove a symbol from user's watchlist."""
    symbol = symbol.strip().upper()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND symbol = ?",
            (user_id, symbol),
        )
        conn.commit()
        return cursor.rowcount > 0
