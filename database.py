"""Database management module for Multi-Platform Price Drop Tracker.

Supports:
- Persistent SQLite storage with Write-Ahead Logging (WAL) for high concurrency
- Configurable DB path via DATABASE_PATH or DATA_DIR env variables (for Railway Volumes)
- Pending product caching for persistent interactive 1-click button clicks
- Full CRUD operations and automated schema migrations
"""

import sqlite3
import os
from typing import List, Dict, Any, Optional

# Configurable DB path for cloud deployment persistence (e.g. Railway Volume mounted at /data)
DATA_DIR = os.getenv("DATA_DIR")
if DATA_DIR:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        pass
    DB_FILE = os.path.join(DATA_DIR, "alerts.db")
elif os.getenv("DATABASE_PATH"):
    DB_FILE = os.getenv("DATABASE_PATH")
else:
    DB_FILE = os.path.join(os.path.dirname(__file__), "alerts.db")

DEFAULT_PINCODE = os.getenv("DEFAULT_PINCODE", "110001")


def get_db_connection() -> sqlite3.Connection:
    """Return a database connection with dictionary-like row factory and WAL mode."""
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA wal_autocheckpoint=1000;")
    return conn


def init_db() -> None:
    """Initialize SQLite tables for tracked products and pending sessions."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tracked_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                platform TEXT DEFAULT 'Amazon',
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

        # User preferences and delivery pincode settings
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                pincode TEXT DEFAULT '110001',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Temporary table to persist 1-click discount button clicks across bot restarts
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_products (
                item_id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                platform_badge TEXT,
                title TEXT NOT NULL,
                price REAL NOT NULL,
                currency TEXT DEFAULT '₹',
                url TEXT NOT NULL,
                image_url TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Check existing columns and migrate if needed
        cursor.execute("PRAGMA table_info(tracked_products)")
        columns = [row["name"] for row in cursor.fetchall()]

        if "platform" not in columns:
            try:
                cursor.execute("ALTER TABLE tracked_products ADD COLUMN platform TEXT DEFAULT 'Amazon'")
            except Exception:
                pass

        if "pincode" not in columns:
            try:
                cursor.execute("ALTER TABLE tracked_products ADD COLUMN pincode TEXT DEFAULT '110001'")
            except Exception:
                pass

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_products_active ON tracked_products (is_active)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_products_user ON tracked_products (user_id, is_active)"
        )
        # Prune stale pending button sessions older than 7 days
        cursor.execute("DELETE FROM pending_products WHERE updated_at < datetime('now', '-7 days')")
        conn.commit()


def save_pending_product(product: Dict[str, Any]) -> None:
    """Save detected product to pending table so button clicks survive bot restarts."""
    if not product or not product.get("item_id"):
        return
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pending_products (
                    item_id, platform, platform_badge, title, price, currency, url, image_url, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(item_id) DO UPDATE SET
                    platform = excluded.platform,
                    platform_badge = excluded.platform_badge,
                    title = excluded.title,
                    price = excluded.price,
                    currency = excluded.currency,
                    url = excluded.url,
                    image_url = excluded.image_url,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    product["item_id"],
                    product.get("platform", "Unknown"),
                    product.get("platform_badge", "📦"),
                    product["title"],
                    product["price"],
                    product.get("currency", "₹"),
                    product["url"],
                    product.get("image_url"),
                ),
            )
            conn.commit()
    except Exception:
        pass


def get_pending_product(item_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve pending product data for button clicks after restart."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT item_id, platform, platform_badge, title, price, currency, url, image_url
                FROM pending_products
                WHERE item_id = ?
                """,
                (item_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def set_user_pincode(user_id: int, pincode: str) -> None:
    """Set or update user's preferred delivery pincode."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_settings (user_id, pincode, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                pincode = excluded.pincode,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, str(pincode).strip()),
        )
        conn.commit()


def get_user_pincode(user_id: int) -> str:
    """Get user's configured delivery pincode or fallback to default."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT pincode FROM user_settings WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            if row and row["pincode"]:
                return str(row["pincode"]).strip()
    except Exception:
        pass
    return DEFAULT_PINCODE


def add_tracked_product(
    user_id: int,
    chat_id: int,
    platform: str,
    item_id: str,
    title: str,
    url: str,
    image_url: Optional[str],
    target_price: float,
    current_price: float,
    currency: str = "₹",
    pincode: Optional[str] = None,
) -> int:
    """Add a new product price drop alert or update target price if already actively tracked."""
    pin = pincode or get_user_pincode(user_id)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Prevent duplicate active trackers for the same user and product
        cursor.execute(
            """
            SELECT id FROM tracked_products
            WHERE user_id = ? AND platform = ? AND asin = ? AND is_active = 1
            LIMIT 1
            """,
            (user_id, platform, item_id),
        )
        existing = cursor.fetchone()
        if existing:
            product_id = existing["id"]
            cursor.execute(
                """
                UPDATE tracked_products
                SET target_price = ?, current_price = ?, url = ?, image_url = ?, currency = ?, pincode = ?
                WHERE id = ?
                """,
                (target_price, current_price, url, image_url, currency, pin, product_id),
            )
            conn.commit()
            return product_id

        cursor.execute(
            """
            INSERT INTO tracked_products (
                user_id, chat_id, platform, asin, title, url, image_url,
                target_price, initial_price, current_price, currency, pincode, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                user_id,
                chat_id,
                platform,
                item_id,
                title,
                url,
                image_url,
                target_price,
                current_price,
                current_price,
                currency,
                pin,
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
            SELECT id, user_id, chat_id, platform, asin AS item_id, title, url, image_url,
                   target_price, initial_price, current_price, currency, pincode, created_at
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
            SELECT id, user_id, chat_id, platform, asin AS item_id, title, url, image_url,
                   target_price, initial_price, current_price, currency, pincode
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
