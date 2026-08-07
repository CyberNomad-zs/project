import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parents[1] / "data" / "bridge.db"
c = sqlite3.connect(db)
c.row_factory = sqlite3.Row
print("available_days distribution (sample)")
for r in c.execute(
    """
    select available, available_days, inv_age_365_plus, count(*) n
    from asin_daily where biz_date='2026-07-21'
    group by available, available_days, inv_age_365_plus
    order by n desc limit 20
    """
):
    print(dict(r))
print("inventory_low red samples")
for r in c.execute(
    """
    select t.shop_name, t.asin, t.level, t.message, a.available, a.available_days
    from anomaly_tasks t
    join asin_daily a on a.biz_date=t.biz_date and a.shop_name=t.shop_name and a.asin=t.asin
    where t.anomaly_type='inventory_low' and t.level='red' limit 8
    """
):
    print(dict(r))
