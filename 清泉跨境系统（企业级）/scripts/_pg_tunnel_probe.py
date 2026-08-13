# -*- coding: utf-8 -*-
"""Probe PG via local tunnel. Usage: python _pg_tunnel_probe.py user password"""
from __future__ import annotations

import asyncio
import sys


async def main() -> int:
    user = sys.argv[1] if len(sys.argv) > 1 else "qingquan"
    password = sys.argv[2] if len(sys.argv) > 2 else "qingquan"
    host = sys.argv[3] if len(sys.argv) > 3 else "127.0.0.1"
    port = int(sys.argv[4] if len(sys.argv) > 4 else "5432")
    db = sys.argv[5] if len(sys.argv) > 5 else "qingquan"
    try:
        import asyncpg
    except ImportError:
        print("FAIL no asyncpg")
        return 2
    try:
        conn = await asyncpg.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database=db,
            timeout=10,
        )
        ver = await conn.fetchval("select version()")
        has_tk = await conn.fetchval(
            "select count(*) from information_schema.schemata where schema_name='tk'"
        )
        anom = None
        try:
            anom = await conn.fetchval("select count(*) from tk.fact_tk_anomaly_task")
        except Exception:
            pass
        await conn.close()
        print(f"OK host={host}:{port} db={db} user={user} tk_schema={has_tk} anomaly_rows={anom}")
        print(f"version={str(ver)[:60]}")
        return 0
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
