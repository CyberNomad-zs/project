"""Apply a multi-statement SQL migration via asyncpg (statement split)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def split_sql(raw: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    in_dollar = False
    for line in raw.splitlines():
        if not in_dollar:
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            if "$$" in line:
                if line.count("$$") == 1:
                    in_dollar = True
                buf.append(line)
                if not in_dollar and stripped.endswith(";"):
                    stmt = "\n".join(buf).strip()
                    if stmt:
                        parts.append(stmt)
                    buf = []
                continue
            buf.append(line)
            if stripped.endswith(";"):
                stmt = "\n".join(buf).strip()
                if stmt:
                    parts.append(stmt)
                buf = []
        else:
            buf.append(line)
            if "$$" in line:
                in_dollar = False
                stmt = "\n".join(buf).strip()
                if stmt:
                    parts.append(stmt)
                buf = []
    if buf:
        stmt = "\n".join(buf).strip()
        if stmt:
            parts.append(stmt)
    return parts


async def main(sql_path: Path, url: str) -> None:
    raw = sql_path.read_text(encoding="utf-8")
    parts = split_sql(raw)
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        for i, s in enumerate(parts, 1):
            print(f"-- exec {i}/{len(parts)} len={len(s)}")
            await conn.execute(text(s))
        n = (
            await conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema='tk' AND table_name='fact_tiktok_content_daily'
                    """
                )
            )
        ).scalar()
        print("table_exists", n)
    await engine.dispose()


if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "migrations/013_tk_content_daily.sql")
    db_url = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "postgresql+asyncpg://qingquan:qingquan@127.0.0.1:5432/qingquan"
    )
    asyncio.run(main(path, db_url))
    print("migration ok")
