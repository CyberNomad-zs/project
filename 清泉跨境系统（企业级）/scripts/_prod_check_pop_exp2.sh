#!/usr/bin/env bash
set -euo pipefail

echo "=== shop dim for pop ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT column_name, data_type FROM information_schema.columns
WHERE table_schema='public' AND table_name='shop' ORDER BY ordinal_position;
"
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT * FROM public.shop WHERE external_id='27758103898326' OR name ILIKE '%Gardena%' OR name ILIKE '%Pop%' LIMIT 10;
" 2>/dev/null || true

echo "=== fact table constraints ==="
docker exec qingquan-db-1 psql -U qingquan -d qingquan -c "
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'tk.fact_tiktok_experience_daily'::regclass;
"

echo "=== try reprocess via python ==="
docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python - <<'PY'
import asyncio, json
from sqlalchemy import text
from app.infra.db import SessionLocal
from app.api.ingest import _process_tiktok_experience_daily
from app.schemas.ingest import IngestEnvelope

async def main():
    async with SessionLocal() as db:
        row = (await db.execute(text("""
            SELECT id::text, payload, shop_external_id, biz_date::text, collected_at
            FROM public.ingest_raw
            WHERE id = '77ad3c0a-3bb7-4b36-979f-e9b273dd0dba'
        """))).mappings().first()
        print("row", dict(row) if row else None)
        if not row:
            return
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        env = IngestEnvelope(
            source="tiktok_experience_daily",
            platform="tiktok",
            shop_id=row["shop_external_id"],
            shop_name="Gardena",
            biz_date=row["biz_date"],
            collected_at=row["collected_at"],
            payload=payload,
        )
        # resolve shop uuid like ingest does
        shop_uuid = None
        try:
            from app.api import ingest as ing
            # find helper
            names = [n for n in dir(ing) if "shop" in n.lower()]
            print("helpers", names[:30])
        except Exception as e:
            print("import helpers", e)
        try:
            await _process_tiktok_experience_daily(db, ingest_id=row["id"], env=env, shop_uuid=shop_uuid)
            await db.commit()
            print("REPROCESS_OK")
        except Exception as e:
            await db.rollback()
            print("REPROCESS_FAIL", type(e), e)
        cnt = (await db.execute(text("SELECT count(*) FROM tk.fact_tiktok_experience_daily WHERE shop_external_id='27758103898326'"))).scalar()
        print("fact_count_pop", cnt)

asyncio.run(main())
PY
