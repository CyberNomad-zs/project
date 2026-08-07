import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parents[1] / "data" / "bridge.db"
c = sqlite3.connect(db)
c.row_factory = sqlite3.Row
print("=== shops ===")
for r in c.execute(
    """
    select shop_name, count(*) n,
           sum(case when owner is null or owner='' then 1 else 0 end) no_owner
    from asin_daily where biz_date='2026-07-21'
    group by shop_name order by n desc
    """
):
    print(dict(r))
print("=== anomaly types ===")
for r in c.execute(
    """
    select anomaly_type, level, count(*) n
    from anomaly_tasks group by anomaly_type, level order by n desc
    """
):
    print(dict(r))
print("=== inventory / rating null ratio ===")
r = c.execute(
    """
    select count(*) total,
           sum(case when available_days is null then 1 else 0 end) null_days,
           sum(case when available is null then 1 else 0 end) null_avail,
           sum(case when rating is null then 1 else 0 end) null_rating
    from asin_daily where biz_date='2026-07-21'
    """
).fetchone()
print(dict(r))
