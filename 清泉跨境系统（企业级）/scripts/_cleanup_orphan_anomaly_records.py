import asyncio, sys
from pathlib import Path
ROOT = Path(r"E:\project\清泉跨境系统（企业级）")
sys.path.insert(0, str(ROOT / "backend"))

async def main():
    from app.config import get_settings
    get_settings.cache_clear()
    from sqlalchemy import text
    from app.infra.db import SessionLocal
    from app.adapters.feishu import bitable
    import httpx
    s = get_settings()
    app_token = s.feishu_bitable_app_token_tk or s.feishu_bitable_app_token
    table_id = s.feishu_bitable_table_tk_anomaly_task
    token = await bitable.get_tenant_access_token()
    # mapped record ids
    async with SessionLocal() as db:
        rows = (await db.execute(text(
            "SELECT record_id FROM sync_feishu_map WHERE table_key='tk_anomaly_task' AND table_id=:t"
        ), {"t": table_id})).fetchall()
        keep = {r[0] for r in rows if r[0]}
    print("keep", len(keep))
    # list all feishu records
    all_ids = []
    page = None
    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records?page_size=500"
            if page:
                url += f"&page_token={page}"
            r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            data = r.json()
            if data.get("code") != 0:
                print("list fail", data)
                return 1
            for it in (data.get("data") or {}).get("items") or []:
                all_ids.append(it.get("record_id"))
            if not (data.get("data") or {}).get("has_more"):
                break
            page = (data.get("data") or {}).get("page_token")
    print("feishu", len(all_ids))
    orphans = [rid for rid in all_ids if rid not in keep]
    print("orphans", len(orphans))
    # batch delete 500
    deleted = 0
    async with httpx.AsyncClient(timeout=60) as client:
        for i in range(0, len(orphans), 500):
            chunk = orphans[i:i+500]
            if not chunk:
                break
            r = await client.post(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_delete",
                headers={"Authorization": f"Bearer {token}"},
                json={"records": chunk},
            )
            data = r.json()
            print("delete", data.get("code"), data.get("msg"), "n=", len(chunk))
            if data.get("code") == 0:
                deleted += len(chunk)
    print("deleted", deleted)
    # final count
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records?page_size=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = r.json()
        print("final_total", (data.get("data") or {}).get("total"))
    return 0
raise SystemExit(asyncio.run(main()))
