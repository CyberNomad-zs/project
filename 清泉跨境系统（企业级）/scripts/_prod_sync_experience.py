import asyncio
import json

from app.infra.db import SessionLocal


async def main() -> None:
    from app.jobs import tk_feishu_sync as m

    names = [a for a in dir(m) if not a.startswith("_")]
    print("exports", names)
    async with SessionLocal() as db:
        if hasattr(m, "sync_one_table"):
            res = await m.sync_one_table(db, "tk_experience_daily")
        elif hasattr(m, "sync_table"):
            res = await m.sync_table(db, table_key="tk_experience_daily")
        elif hasattr(m, "run_sync"):
            res = await m.run_sync(db, tables=["tk_experience_daily"])
        else:
            # fall back: search for callable taking table_key
            res = {"error": "no known sync entry", "exports": names}
            print(json.dumps(res, ensure_ascii=False, default=str))
            return
        print(json.dumps(res, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
