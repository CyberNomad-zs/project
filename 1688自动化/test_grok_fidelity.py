# -*- coding: utf-8 -*-
"""测 grok 图生图在"强制保真"prompt 下能否保住产品原样。"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.generate.zapi_client import ZapiClient, ROOT

client = ZapiClient()
clean = ROOT / "文件" / "易之来灯具" / "G125TBOA" / "49462ac2-deaf-42e4-93c9-25aad01a73a2.png"
out_dir = ROOT / "output" / "_grok_fidelity"

# 强制保真：只换背景，产品任何细节不许动
prompt_keep = (
    "严格保持这盏灯泡的外形轮廓、玻璃形状、琥珀色泽、内部灯丝走向、金属灯头、"
    "整体比例与原图完全一致，禁止改变产品的任何细节和造型；"
    "仅将背景替换为纯白色#FFFFFF，产品居中，1:1正方形，"
    "无任何文字、字母、数字、logo、水印、边框"
)
t0 = time.time()
out = client.edit_image(clean, prompt_keep, out_dir / "grok_keep.jpg")
print(f"grok强制保真: {out}  ({out.stat().st_size/1024:.0f}KB, {time.time()-t0:.1f}s)")
