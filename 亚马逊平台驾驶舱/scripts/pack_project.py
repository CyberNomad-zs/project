# -*- coding: utf-8 -*-
"""Pack project into zip excluding venv, secrets, caches."""
from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime.now().strftime("%Y%m%d_%H%M")
OUT = ROOT / f"亚马逊ASIN健康度驾驶舱_项目包_{STAMP}.zip"

SKIP_DIRS = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".playwright-mcp",
    "_api_docs",
    "node_modules",
    ".mypy_cache",
    ".idea",
    ".vscode",
}
SKIP_FILES = {
    ".env",
    ".env.local",
}
SKIP_SUFFIX = {".pyc", ".pyo"}
SKIP_PREFIX = ("~$",)
SKIP_NAME_CONTAINS_ZIP = True  # don't nest previous packs


def should_skip(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    parts = rel.parts
    if any(p in SKIP_DIRS for p in parts):
        return True
    name = path.name
    if name in SKIP_FILES:
        return True
    if path.suffix.lower() in SKIP_SUFFIX:
        return True
    if name.startswith(SKIP_PREFIX):
        return True
    if SKIP_NAME_CONTAINS_ZIP and name.endswith(".zip") and "项目包" in name:
        return True
    return False


def main() -> None:
    files: list[Path] = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if should_skip(p, ROOT):
            continue
        files.append(p)

    note = f"""【打包说明】
1. 本压缩包已排除：.venv、__pycache__、.env（密钥）、.pytest_cache、.git、历史项目包 zip 等
2. 解压后请执行：
   python -m venv .venv
   .\\.venv\\Scripts\\Activate.ps1
   pip install -r requirements.txt
   copy .env.example .env
   # 填写赛狐 / 飞书凭证后再运行
3. 领导汇报材料：
   docs\\ASIN健康度项目进展汇报.pptx
   docs\\项目进展汇报-ASIN健康度监控与运营闭环.md
4. 飞书操作手册：docs\\飞书协作者与动作表操作手册.md
5. 日批说明：docs\\日批与机器人.md
6. 打包时间：{STAMP}
7. 文件数：{len(files)}
"""

    if OUT.exists():
        OUT.unlink()

    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # readme first
        zf.writestr("亚马逊平台驾驶舱-店铺数据/【解压必读】.txt", note.encode("utf-8-sig"))
        for f in sorted(files):
            arc = Path("亚马逊平台驾驶舱-店铺数据") / f.relative_to(ROOT)
            zf.write(f, arcname=str(arc).replace("\\", "/"))

    size_mb = OUT.stat().st_size / (1024 * 1024)
    print(f"ZIP={OUT}")
    print(f"SIZE_MB={size_mb:.2f}")
    print(f"FILES={len(files)}")


if __name__ == "__main__":
    main()
