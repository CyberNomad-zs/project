import asyncio
import json

from app.infra.db import SessionLocal
from app.jobs.tk_feishu_sync import sync_table


async def main() -> None:
    async with SessionLocal() as db:
        res = await sync_table(db, table_key="tk_experience_daily", mode="full", lookback_days=30)
        print(json.dumps(res, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
