import asyncio, logging, sys
from pathlib import Path
ROOT = Path(r"E:\project\清泉跨境系统（企业级）")
sys.path.insert(0, str(ROOT / "backend"))
logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("app.jobs.tk_feishu_sync").setLevel(logging.INFO)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

async def main():
    from app.config import get_settings
    get_settings.cache_clear()
    s = get_settings()
    print("table=", s.feishu_bitable_table_tk_anomaly_task)
    from sqlalchemy import text
    from app.infra.db import SessionLocal
    from app.jobs.tk_feishu_sync import sync_table
    async with SessionLocal() as db:
        r = await db.execute(text("DELETE FROM sync_feishu_map WHERE table_key = 'tk_anomaly_task'"))
        await db.commit()
        print("cleared_main_map rowcount=", r.rowcount)
        stats = await sync_table(db, table_key="tk_anomaly_task", lookback_days=90, limit=5000, dry_run=False)
        print("STATS", stats)
        nmap = (await db.execute(text("SELECT count(*) FROM sync_feishu_map WHERE table_key='tk_anomaly_task'"))).scalar()
        print("map_main_after", nmap)
        await db.commit()
    print("DONE")
asyncio.run(main())
