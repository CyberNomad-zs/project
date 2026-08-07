# -*- coding: utf-8 -*-
"""扫真实产品目录：统计每个型号有几张"干净白底图"(类型A)可做非生成式主图。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.generate.image import is_clean_white_bg
from src.generate.zapi_client import ROOT

base = ROOT / "文件" / "易之来灯具"
IMG_EXT = {".png", ".jpg", ".jpeg", ".jfif"}

rows = []
for d in sorted([p for p in base.iterdir() if p.is_dir()]):
    imgs = [f for f in d.iterdir() if f.suffix.lower() in IMG_EXT]
    if not imgs:
        continue
    clean = 0
    for f in imgs:
        try:
            if is_clean_white_bg(f):
                clean += 1
        except Exception:
            pass
    rows.append((d.name, len(imgs), clean))

print(f"{'型号':<28}{'总图':>6}{'干净白底':>10}")
print("-" * 46)
enough = 0
for name, total, clean in rows:
    flag = "  <2!" if clean < 2 else ""
    print(f"{name:<28}{total:>6}{clean:>10}{flag}")
    if clean >= 2:
        enough += 1
print("-" * 46)
print(f"型号数 {len(rows)}，其中 ≥2张干净白底图的 {enough} 个（占 {enough/max(1,len(rows))*100:.0f}%）")
