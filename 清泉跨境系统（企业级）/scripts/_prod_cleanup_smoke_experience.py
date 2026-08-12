"""清理 SMOKE 体验分测试行：飞书记录 + sync_feishu_map + PG 事实行。"""
import asyncio
import json
import os

import httpx

APP_ID = os.environ["FEISHU_APP_ID"]
APP_SECRET = os.environ["FEISHU_APP_SECRET"]
APP_TOKEN = os.environ["FEISHU_BITABLE_APP_TOKEN_TK"]
TABLE_ID = os.environ["FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY"]
BASE = "https://open.feishu.cn/open-apis"

RECORD_IDS = ["recvs4AyTMLQMh", "recvs4AztBjvHt"]
LOCAL_IDS = ["231f5296-e536-4cb0-90ab-56c45e327814", "b1e514f7-e223-40ea-adb4-e29ed73dfa1c"]


async def main() -> None:
    async with httpx.AsyncClient(timeout=20) as cli:
        r = await cli.post(
            f"{BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": APP_ID, "app_secret": APP_SECRET},
        )
        token = r.json()["tenant_access_token"]
        h = {"Authorization": f"Bearer {token}"}
        r = await cli.post(
            f"{BASE}/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/batch_delete",
            headers=h,
            json={"records": RECORD_IDS},
        )
        print("feishu batch_delete:", json.dumps(r.json(), ensure_ascii=False)[:300])

    from app.infra.db import SessionLocal
    from sqlalchemy import text

    async with SessionLocal() as db:
        res1 = await db.execute(
            text("DELETE FROM public.sync_feishu_map WHERE table_key='tk_experience_daily' AND local_id::text = ANY(:ids)"),
            {"ids": LOCAL_IDS},
        )
        res2 = await db.execute(
            text("DELETE FROM tk.fact_tiktok_experience_daily WHERE id::text = ANY(:ids)"),
            {"ids": LOCAL_IDS},
        )
        await db.commit()
        print("map deleted:", res1.rowcount, "fact deleted:", res2.rowcount)


if __name__ == "__main__":
    asyncio.run(main())
