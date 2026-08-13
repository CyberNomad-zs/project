import asyncio, logging, sys
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
ROOT = Path(r"E:\project\清泉跨境系统（企业级）")
sys.path.insert(0, str(ROOT / "backend"))
logging.basicConfig(level=logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)

async def main():
    from app.config import get_settings
    get_settings.cache_clear()
    from sqlalchemy import text
    from app.infra.db import SessionLocal
    from app.jobs.tk_feishu_sync import (
        TABLE_SPECS, _upsert_rows_to_feishu, resolve_tk_app_token, resolve_table_id
    )
    from app.adapters.feishu import bitable
    s = get_settings()
    tid = resolve_table_id("tk_anomaly_task", s)
    app_token = resolve_tk_app_token(s)
    print("table", tid)
    async with SessionLocal() as db:
        nmap = (await db.execute(text("SELECT count(*) FROM sync_feishu_map WHERE table_key='tk_anomaly_task'"))).scalar()
        print("map_before", nmap)
        total = (await db.execute(text("SELECT count(*) FROM tk.fact_tk_anomaly_task"))).scalar()
        print("pg_total", total)
        spec = TABLE_SPECS["tk_anomaly_task"]
        since = datetime.now(timezone.utc) - timedelta(days=90)
        bind = {
            "filter_biz": False,
            "filter_since": True,
            "biz_date": date(1970, 1, 1),
            "since": since,
            "since_date": since.date(),
            "lim": 5000,
        }
        rows = (await db.execute(text(spec["select"]), bind)).mappings().all()
        print("rows", len(rows))
        token = await bitable.get_tenant_access_token()
        st = await _upsert_rows_to_feishu(
            db,
            rows=list(rows),
            mapper=spec["mapper"],
            token=token,
            app_token=app_token,
            table_id=tid,
            map_table_key="tk_anomaly_task",
            local_table=spec["local_table"],
        )
        print("MAIN_STATS", st)
        nmap2 = (await db.execute(text("SELECT count(*) FROM sync_feishu_map WHERE table_key='tk_anomaly_task'"))).scalar()
        print("map_after", nmap2)
        await db.commit()
    print("DONE")
asyncio.run(main())
