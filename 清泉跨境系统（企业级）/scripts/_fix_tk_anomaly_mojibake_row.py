# -*- coding: utf-8 -*-
"""Fix one smoke-row mojibake in tk.fact_tk_anomaly_task then print row."""
from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
TASK_KEY = "T20260804-02216807-PID-DISH-001-product_stock_low"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


async def main() -> int:
    env = load_env()
    url = env["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        await conn.execute(
            """
            UPDATE tk.fact_tk_anomaly_task
            SET product_name_cn = $1,
                summary = $2,
                description = $3,
                progress_note = $4,
                updated_at = now()
            WHERE task_key = $5
            """,
            "沥水架",
            "商品库存不足 · Dish Rack（联调样例）",
            "可售库存不足联调样例 | product_id=PID-DISH-001 | 中文名已修复",
            "可售库存 2 < 补货阈值 10（联调样例）",
            TASK_KEY,
        )
        row = await conn.fetchrow(
            """
            SELECT task_key, product_name, product_name_cn, summary, progress_note,
                   convert_to(product_name_cn, 'UTF8') AS cn_bytes,
                   convert_to(progress_note, 'UTF8') AS pn_bytes
            FROM tk.fact_tk_anomaly_task
            WHERE task_key = $1
            """,
            TASK_KEY,
        )
        assert row is not None
        print("task_key", row["task_key"])
        print("product_name", row["product_name"])
        print("product_name_cn", row["product_name_cn"])
        print("cn_bytes", list(row["cn_bytes"] or b""))
        print("summary", row["summary"])
        print("progress_note", row["progress_note"])
        print("pn_bytes", list(row["pn_bytes"] or b""))
        if row["product_name_cn"] != "沥水架":
            print("FAIL still wrong cn")
            return 1
        if not row["progress_note"] or "?" in str(row["progress_note"]):
            print("FAIL still wrong progress_note")
            return 1
        print("OK")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
