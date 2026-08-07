# -*- coding: utf-8 -*-
"""M1 主图归一化测试：验证分类 + 保真归一化。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.generate.image import is_clean_white_bg, make_main_image
from src.generate.zapi_client import ROOT

poster = ROOT / "文件" / "易之来灯具" / "A60OFA" / "04ae6462-67f2-4aec-b8ac-920d4c9b08e9.png"
clean = ROOT / "文件" / "易之来灯具" / "G125TBOA" / "49462ac2-deaf-42e4-93c9-25aad01a73a2.png"
out_dir = ROOT / "output" / "_main_test"

print("分类判断（is_clean_white_bg）：")
print(f"  卖点海报(A60OFA)  -> {is_clean_white_bg(poster)}   (期望 False)")
print(f"  干净产品图(G125)  -> {is_clean_white_bg(clean)}   (期望 True)")

out = make_main_image(clean, out_dir / "G125_main.jpg", target_size=(800, 800))
size_kb = out.stat().st_size / 1024
print(f"\n归一化输出: {out}  ({size_kb:.0f} KB)")
