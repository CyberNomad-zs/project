"""Mark stuck sync_runs (status=running) as failed."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

db = Path(__file__).resolve().parents[1] / "data" / "bridge.db"
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
c = sqlite3.connect(db)
rows = c.execute(
    "SELECT id, biz_date, started_at FROM sync_runs WHERE status='running'"
).fetchall()
print("stale running:", rows)
if rows:
    c.execute(
        """
        UPDATE sync_runs
        SET status='failed', finished_at=?, error=?
        WHERE status='running'
        """,
        (now, "stale running cleaned after scheduler failure"),
    )
    c.commit()
    print("cleaned", len(rows))
else:
    print("nothing to clean")
c.close()
