from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .. import util


class Budgets:
    """Per-provider rolling-window usage, persisted in SQLite."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = str(path or (util.DATA_DIR / "gateway.db"))
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    status TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_provider_ts ON events(provider, ts)")

    def record(
        self,
        provider: str,
        model: str,
        status: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO events(ts, provider, model, status, prompt_tokens, completion_tokens) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    util.now_utc(),
                    provider,
                    model,
                    status,
                    max(0, int(prompt_tokens or 0)),
                    max(0, int(completion_tokens or 0)),
                ),
            )

    def _window(self, provider: str, seconds: int) -> tuple[int, int]:
        since = (datetime.now(timezone.utc) - timedelta(seconds=seconds)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(prompt_tokens + completion_tokens), 0) "
                "FROM events WHERE provider = ? AND ts >= ?",
                (provider, since),
            ).fetchone()
        return int(row[0] or 0), int(row[1] or 0)

    def allow(self, provider: str, limits: dict | None, estimate_tokens: int = 0) -> bool:
        limits = limits or {}
        checks = (
            ("rpm", 60, 0, 1),
            ("rpd", 86400, 0, 1),
            ("tpm", 60, 1, estimate_tokens),
            ("tpd", 86400, 1, estimate_tokens),
        )
        for key, seconds, field, extra in checks:
            limit = limits.get(key)
            if not limit:
                continue
            requests, tokens = self._window(provider, seconds)
            value = requests if field == 0 else tokens
            if value + extra > int(limit):
                return False
        return True

    def stats(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT provider, COUNT(*), SUM(prompt_tokens + completion_tokens) "
                "FROM events GROUP BY provider"
            ).fetchall()
        return {
            row[0]: {"requests": int(row[1] or 0), "tokens": int(row[2] or 0)}
            for row in rows
        }
