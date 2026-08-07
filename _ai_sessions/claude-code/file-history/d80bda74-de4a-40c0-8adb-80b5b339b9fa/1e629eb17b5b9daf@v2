import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parents[1] / "data" / "bridge.db"
c = sqlite3.connect(db)
print("asin_daily", c.execute("select count(*) from asin_daily").fetchone()[0])
print(
    "tasks_total",
    c.execute("select count(*) from anomaly_tasks").fetchone()[0],
)
print(
    "tasks_open",
    c.execute(
        "select count(*) from anomaly_tasks where status not in ('closed','resolved')"
    ).fetchone()[0],
)
print("by level", c.execute("select level, count(*) from anomaly_tasks group by level").fetchall())
print(
    "sync_runs",
    c.execute(
        "select id,biz_date,status,total_rows from sync_runs order by id desc limit 5"
    ).fetchall(),
)
