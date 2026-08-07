# -*- coding: utf-8 -*-
"""测 M1 主视频：拿 G125 已生成的主图当首帧，生成一段 5s 主图视频。"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.generate.video import make_product_video, pick_first_frame
from src.generate.zapi_client import ROOT

product_dir = ROOT / "output" / "_product_G125TBOA"
ff = pick_first_frame(product_dir)
print(f"首帧: {ff.name}")
t0 = time.time()
out = make_product_video(product_dir, product_dir / "main_video.mp4", first_frame=ff, seconds=5)
mb = out.stat().st_size / 1024 / 1024
print(f"主视频完成: {out}  ({mb:.1f}MB, {time.time()-t0:.0f}s)")
