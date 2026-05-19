import sqlite3
import os
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "player_history.db"
)


def _get_db_path() -> str:
    return DB_PATH


@contextmanager
def _get_conn():
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                tier TEXT DEFAULT 'Gold',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS player (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                puuid TEXT UNIQUE NOT NULL,
                game_name TEXT NOT NULL,
                tag_line TEXT NOT NULL,
                last_updated TEXT
            );

            CREATE TABLE IF NOT EXISTS match_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                match_id TEXT NOT NULL,
                game_start_timestamp TEXT,
                kda REAL,
                acs REAL,
                kast REAL,
                headshot_percent REAL,
                first_blood_rate REAL,
                econ_rating REAL,
                agent_played TEXT,
                map_name TEXT,
                won INTEGER,
                FOREIGN KEY (player_id) REFERENCES player(id),
                UNIQUE(player_id, match_id)
            );

            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                player_name TEXT,
                report_html TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                stripe_session_id TEXT,
                amount REAL,
                currency TEXT DEFAULT 'cny',
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)


def register_user(email: str, password: str) -> Optional[int]:
    hashed = generate_password_hash(password)
    try:
        with _get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO users (email, password) VALUES (?, ?)",
                (email, hashed)
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def login_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        cursor = conn.execute(
            "SELECT id, email, password, created_at, tier FROM users WHERE email = ?",
            (email,)
        )
        row = cursor.fetchone()
        if row is None:
            return None

        stored = row["password"]
        # Check if stored hash is a modern werkzeug hash (contains $)
        if len(stored) >= 20 and "$" in stored:
            if not check_password_hash(stored, password):
                return None
        else:
            # Legacy plaintext comparison
            if stored != password:
                return None
            # Auto-upgrade legacy password to hashed version
            hashed = generate_password_hash(password)
            conn.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (hashed, row["id"])
            )

        return {
            "id": row["id"],
            "email": row["email"],
            "created_at": row["created_at"],
            "tier": row["tier"]
        }


def upsert_player(puuid: str, game_name: str, tag_line: str) -> int:
    with _get_conn() as conn:
        cursor = conn.execute(
            "SELECT id FROM player WHERE puuid = ?", (puuid,)
        )
        row = cursor.fetchone()
        if row:
            conn.execute(
                "UPDATE player SET game_name = ?, tag_line = ?, last_updated = ? WHERE puuid = ?",
                (game_name, tag_line, datetime.now().isoformat(), puuid)
            )
            return row["id"]
        else:
            cursor = conn.execute(
                "INSERT INTO player (puuid, game_name, tag_line, last_updated) VALUES (?, ?, ?, ?)",
                (puuid, game_name, tag_line, datetime.now().isoformat())
            )
            return cursor.lastrowid


def save_match_records(puuid: str, game_name: str, tag_line: str, matches_data: List[Dict[str, Any]]):
    player_id = upsert_player(puuid, game_name, tag_line)
    with _get_conn() as conn:
        for m in matches_data:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO match_history
                    (player_id, match_id, game_start_timestamp, kda, acs, kast,
                     headshot_percent, first_blood_rate, econ_rating, agent_played, map_name, won)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id,
                    m.get("match_id"),
                    m.get("game_start_timestamp"),
                    m.get("kda"),
                    m.get("acs"),
                    m.get("kast"),
                    m.get("headshot_percent"),
                    m.get("first_blood_rate"),
                    m.get("econ_rating"),
                    m.get("agent_played"),
                    m.get("map_name"),
                    1 if m.get("won") else 0,
                ))
            except Exception:
                continue


def get_player_history(puuid: str, metric: str, limit: int = 20) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        cursor = conn.execute("""
            SELECT m.{metric} as value, m.game_start_timestamp as date, m.agent_played, m.map_name, m.won
            FROM match_history m
            JOIN player p ON m.player_id = p.id
            WHERE p.puuid = ? AND m.{metric} IS NOT NULL
            ORDER BY m.game_start_timestamp ASC
            LIMIT ?
        """.format(metric=metric), (puuid, limit))
        return [dict(row) for row in cursor.fetchall()]


def get_player_puuid(game_name: str, tag_line: str) -> Optional[str]:
    with _get_conn() as conn:
        cursor = conn.execute(
            "SELECT puuid FROM player WHERE game_name = ? AND tag_line = ?",
            (game_name, tag_line)
        )
        row = cursor.fetchone()
        return row["puuid"] if row else None


def is_cache_valid(puuid: str, max_age_minutes: int = 30) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute(
            "SELECT last_updated FROM player WHERE puuid = ?",
            (puuid,)
        )
        row = cursor.fetchone()
        if row is None or row["last_updated"] is None:
            return False
        last_updated = datetime.fromisoformat(row["last_updated"])
        return datetime.now() - last_updated < timedelta(minutes=max_age_minutes)


def get_cached_metrics(puuid: str) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        cursor = conn.execute("""
            SELECT m.kda, m.acs, m.kast, m.headshot_percent,
                   m.first_blood_rate, m.econ_rating,
                   m.match_id, m.agent_played, m.map_name
            FROM match_history m
            JOIN player p ON m.player_id = p.id
            WHERE p.puuid = ?
            ORDER BY m.game_start_timestamp ASC
        """, (puuid,))
        return [dict(row) for row in cursor.fetchall()]


def save_report(user_id: int, player_name: str, report_html: str) -> int:
    with _get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO reports (user_id, player_name, report_html) VALUES (?, ?, ?)",
            (user_id, player_name, report_html)
        )
        return cursor.lastrowid


def get_user_reports(user_id: int) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        cursor = conn.execute("""
            SELECT id, player_name, created_at FROM reports
            WHERE user_id = ? ORDER BY created_at DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_report_by_id(report_id: int) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        cursor = conn.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def has_user_paid(user_id: int) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) as cnt FROM payments WHERE user_id = ? AND status = 'completed'",
            (user_id,)
        )
        row = cursor.fetchone()
        return row["cnt"] > 0


def record_payment(user_id: int, session_id: str, amount: float = 9.9):
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO payments (user_id, stripe_session_id, amount, status)
            VALUES (?, ?, ?, 'completed')
        """, (user_id, session_id, amount))


def update_user_tier(user_id: int, tier: str):
    with _get_conn() as conn:
        conn.execute(
            "UPDATE users SET tier = ? WHERE id = ?",
            (tier, user_id)
        )


def seed_admin_account():
    with _get_conn() as conn:
        cursor = conn.execute("SELECT id FROM users WHERE email = ?", ("admin@valcoach.gg",))
        row = cursor.fetchone()
        if row:
            hashed = generate_password_hash("admin123")
            conn.execute("UPDATE users SET password = ?, tier = 'admin' WHERE id = ?", (hashed, row["id"]))
            return row["id"]
        hashed = generate_password_hash("admin123")
        cursor = conn.execute(
            "INSERT INTO users (email, password, tier) VALUES (?, ?, 'admin')",
            ("admin@valcoach.gg", hashed)
        )
        return cursor.lastrowid
