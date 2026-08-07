# -*- coding: utf-8 -*-
"""端到端测：一个真实商品目录 -> 5 张主图。"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.generate.image import make_product_mains
from src.generate.zapi_client import ROOT

product_dir = ROOT / "文件" / "易之来灯具" / "G125TBOA"
out_dir = ROOT / "output" / "_product_G125TBOA"

t0 = time.time()
res = make_product_mains(product_dir, out_dir)
print(f"\n商品 G125TBOA 主图产出（用时 {time.time()-t0:.0f}s）：")
for slot, path in res.items():
    if path:
        kb = Path(path).stat().st_size / 1024
        print(f"  {slot:<20} -> {Path(path).name}  ({kb:.0f}KB)")
    else:
        print(f"  {slot:<20} -> (缺)")
