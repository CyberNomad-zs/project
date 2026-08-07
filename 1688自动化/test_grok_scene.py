# -*- coding: utf-8 -*-
"""测 grok：把真实产品放进场景，同时强制保住产品原样（场景/卖点主图用）。"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.generate.zapi_client import ZapiClient, ROOT

client = ZapiClient()
clean = ROOT / "文件" / "易之来灯具" / "G125TBOA" / "49462ac2-deaf-42e4-93c9-25aad01a73a2.png"
out_dir = ROOT / "output" / "_grok_scene"

prompt_scene = (
    "严格保持这盏灯泡的外形轮廓、球形玻璃、琥珀色泽、内部双环灯丝走向、金属灯头与整体比例"
    "与原图完全一致，禁止改变产品任何造型和细节；"
    "将其点亮，安放在温馨复古的室内场景中（木质边桌、暖色氛围、虚化背景），"
    "营造家居氛围感，电商卖点主图风格，1:1正方形，画面无任何文字、logo、水印"
)
t0 = time.time()
out = client.edit_image(clean, prompt_scene, out_dir / "grok_scene.jpg")
print(f"grok场景保真: {out}  ({out.stat().st_size/1024:.0f}KB, {time.time()-t0:.1f}s)")
