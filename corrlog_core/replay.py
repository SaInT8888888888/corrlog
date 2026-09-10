"""Persistent admission guard, separate from unauthenticated JSONL transport."""
import sqlite3
from . import verify_trusted, canonical_json


class ReplayGuard:
    """At-most-once admission per correctionId in a trusted local SQLite database.

    Retain and protect the database across restarts. All consumers in the same
    admission domain must use this same database. Deleting/restoring it resets
    protection. This does not detect the same event signed under a fresh ID,
    implement a distributed service, or make downstream side effects atomic.
    """
    def __init__(self, path: str):
        self.path = path
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS admitted (id TEXT PRIMARY KEY, record BLOB NOT NULL)")

    def accept(self, record, public_key) -> bool:
        # Freeze caller-owned data before validation and persistence.
        import copy
        try:
            record = copy.deepcopy(record)
            if not verify_trusted(record, public_key):
                return False
            data = canonical_json(record)
        except Exception:
            return False
        with sqlite3.connect(self.path, timeout=30) as db:
            try:
                db.execute("INSERT INTO admitted(id, record) VALUES (?, ?)",
                           (record["correctionId"], data))
            except sqlite3.IntegrityError:
                return False
        return True
