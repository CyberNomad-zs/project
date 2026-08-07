# -*- coding: utf-8 -*-
"""测 M1 详情页：G125TBOA 源海报 + 已生成主图 -> 详情段图。"""
import sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.generate.detail import make_product_detail
from src.generate.zapi_client import ROOT

src = ROOT / "文件" / "易之来灯具" / "G125TBOA"
out = ROOT / "output" / "_product_G125TBOA"
segs = make_product_detail(src, out)
print(f"详情段图 {len(segs)} 张：")
for s in segs:
    im = Image.open(s)
    print(f"  {s.name}  {im.width}x{im.height}  ({s.stat().st_size/1024:.0f}KB)")
