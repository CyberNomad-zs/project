# -*- coding: utf-8 -*-
"""Pack private project zip INCLUDING .env secrets. For internal use only."""
from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime.now().strftime("%Y%m%d_%H%M")
OUT = ROOT / f"【私密】亚马逊ASIN健康度_含密钥_{STAMP}.zip"

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
# Include .env — this is the private pack
SKIP_FILES: set[str] = set()
SKIP_SUFFIX = {".pyc", ".pyo"}
SKIP_PREFIX = ("~$",)


def should_skip(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if any(p in SKIP_DIRS for p in rel.parts):
        return True
    name = path.name
    if name in SKIP_FILES:
        return True
    if path.suffix.lower() in SKIP_SUFFIX:
        return True
    if name.startswith(SKIP_PREFIX):
        return True
    # nest neither public nor private previous packs
    if name.endswith(".zip") and (
        "项目包" in name or "含密钥" in name or name.startswith("【私密】")
    ):
        return True
    return False


def main() -> None:
    files: list[Path] = []
    has_env = (ROOT / ".env").is_file()
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if should_skip(p, ROOT):
            continue
        files.append(p)

    note = f"""【私密包 — 含密钥 — 严禁外传】

⚠ 本压缩包包含 .env 中的生产/联调凭证：
  - 赛狐 client_id / client_secret
  - 飞书 app_id / app_secret / 多维表 token
  - 飞书机器人 Webhook

使用规范：
1. 仅限公司内网、授权同事；禁止发到公开群、网盘外链、私人微信（非工作号）
2. 传输建议：加密压缩 / 企业网盘权限可控目录 / 当面拷贝
3. 使用完毕后，如设备非专用，请删除本 zip 与解压目录中的 .env
4. 若密钥曾泄露，请立即在赛狐/飞书后台轮换密钥并更新 .env

解压后：
  python -m venv .venv
  .\\.venv\\Scripts\\Activate.ps1
  pip install -r requirements.txt
  # .env 已在包内，一般无需再 copy
  python -m app.main status

汇报材料：
  docs\\ASIN健康度项目进展汇报.pptx
  docs\\项目进展汇报-ASIN健康度监控与运营闭环.md

打包时间：{STAMP}
是否含 .env：{"是" if has_env else "否（未找到 .env）"}
文件数：{len(files)}
"""

    if not has_env:
        print("WARNING: .env not found — package will not contain secrets")

    if OUT.exists():
        OUT.unlink()

    root_name = "亚马逊平台驾驶舱-店铺数据_私密"
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr(
            f"{root_name}/【私密-含密钥-严禁外传】.txt",
            note.encode("utf-8-sig"),
        )
        for f in sorted(files):
            arc = Path(root_name) / f.relative_to(ROOT)
            zf.write(f, arcname=str(arc).replace("\\", "/"))

    size_mb = OUT.stat().st_size / (1024 * 1024)
    print(f"ZIP={OUT}")
    print(f"SIZE_MB={size_mb:.2f}")
    print(f"FILES={len(files)}")
    print(f"HAS_ENV={has_env}")


if __name__ == "__main__":
    main()
