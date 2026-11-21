"""SQLite connection and schema management for Smart Library RecSys."""

from pathlib import Path
import sqlite3
from typing import Iterator

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "library.db"


def get_connection() -> sqlite3.Connection:
    """Return a configured SQLite connection."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    """Create application tables and indexes when they do not exist."""
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL CHECK (role IN ('anggota', 'petugas', 'pengelola')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                category TEXT NOT NULL,
                synopsis TEXT NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
                total_stock INTEGER NOT NULL DEFAULT 0 CHECK (total_stock >= 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS borrowings (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                borrowed_at TEXT NOT NULL,
                returned_at TEXT,
                status TEXT NOT NULL CHECK (status IN ('dipinjam', 'dikembalikan')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_borrowings_user ON borrowings(user_id);
            CREATE INDEX IF NOT EXISTS idx_borrowings_book ON borrowings(book_id);
            CREATE INDEX IF NOT EXISTS idx_borrowings_status ON borrowings(status);
            """
        )


def iter_rows(query: str, parameters: tuple = ()) -> Iterator[sqlite3.Row]:
    """Yield rows for small read-only helper queries."""
    with get_connection() as connection:
        yield from connection.execute(query, parameters).fetchall()
