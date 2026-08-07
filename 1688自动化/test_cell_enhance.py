# -*- coding: utf-8 -*-
"""验证：画册页裁出产品格子 -> grok 强制保真清成白底影棚高清图。"""
import sys, time
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.generate.zapi_client import ZapiClient, ROOT

page = ROOT / "商品数据" / "01 PORTABLE LAMP 便携式灯具 (页5-59)" / "FT3D056" / "主图" / "page_011.png"
out_dir = ROOT / "output" / "_cell_enhance"
out_dir.mkdir(parents=True, exist_ok=True)

# 裁出 FT3D056 产品格子（不含标签文字）
cell = Image.open(page).convert("RGB").crop((600, 408, 800, 600))
cell_path = out_dir / "cell_raw.png"
cell.save(cell_path)
print(f"裁出格子: {cell.size}")

client = ZapiClient()
prompt = (
    "严格保持这个台灯的外形轮廓、白色波浪纹理灯罩、黑色三脚架底座、整体比例与原图完全一致，"
    "禁止改变产品任何造型和细节；将背景替换为纯白色#FFFFFF影棚背景，"
    "产品居中，提升清晰度与质感为高清电商主图，1:1正方形，画面无任何文字、logo、水印"
)
t0 = time.time()
out = client.edit_image(cell_path, prompt, out_dir / "cell_enhanced.jpg")
print(f"grok清图完成: {out}  ({out.stat().st_size/1024:.0f}KB, {time.time()-t0:.1f}s)")
