"""Database management module for Amazon Price Drop Tracker Bot."""

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
    """Initialize SQLite tables for Amazon product tracking."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tracked_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                asin TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                image_url TEXT,
                target_price REAL NOT NULL,
                initial_price REAL NOT NULL,
                current_price REAL NOT NULL,
                currency TEXT DEFAULT '₹',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checked_at TIMESTAMP NULL,
                is_active INTEGER DEFAULT 1,
                triggered_at TIMESTAMP NULL
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_products_active ON tracked_products (is_active)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_products_user ON tracked_products (user_id, is_active)"
        )
        conn.commit()


def add_tracked_product(
    user_id: int,
    chat_id: int,
    asin: str,
    title: str,
    url: str,
    image_url: Optional[str],
    target_price: float,
    current_price: float,
    currency: str = "₹",
) -> int:
    """Add a new product price drop alert to the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tracked_products (
                user_id, chat_id, asin, title, url, image_url,
                target_price, initial_price, current_price, currency, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                user_id,
                chat_id,
                asin,
                title,
                url,
                image_url,
                target_price,
                current_price,
                current_price,
                currency,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_user_products(user_id: int) -> List[Dict[str, Any]]:
    """Retrieve all active tracked products for a specific user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, chat_id, asin, title, url, image_url,
                   target_price, initial_price, current_price, currency, created_at
            FROM tracked_products
            WHERE user_id = ? AND is_active = 1
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_all_active_products() -> List[Dict[str, Any]]:
    """Retrieve all active tracked products across all users for background checking."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, chat_id, asin, title, url, image_url,
                   target_price, initial_price, current_price, currency
            FROM tracked_products
            WHERE is_active = 1
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def update_product_price(product_id: int, new_price: float) -> None:
    """Update the latest known price for a tracked product."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE tracked_products
            SET current_price = ?, last_checked_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_price, product_id),
        )
        conn.commit()


def mark_product_triggered(product_id: int, drop_price: float) -> None:
    """Mark a product alert as triggered so user is not repeatedly spammed."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE tracked_products
            SET is_active = 0,
                current_price = ?,
                triggered_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (drop_price, product_id),
        )
        conn.commit()


def delete_tracked_product(product_id: int, user_id: Optional[int] = None) -> bool:
    """Delete (deactivate) a tracked product by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if user_id is not None:
            cursor.execute(
                "UPDATE tracked_products SET is_active = 0 WHERE id = ? AND user_id = ?",
                (product_id, user_id),
            )
        else:
            cursor.execute(
                "UPDATE tracked_products SET is_active = 0 WHERE id = ?",
                (product_id,),
            )
        conn.commit()
        return cursor.rowcount > 0


def clear_user_products(user_id: int) -> int:
    """Clear all active tracked products for a user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tracked_products SET is_active = 0 WHERE user_id = ? AND is_active = 1",
            (user_id,),
        )
        conn.commit()
        return cursor.rowcount
