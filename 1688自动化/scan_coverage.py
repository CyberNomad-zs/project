# -*- coding: utf-8 -*-
"""统计 837 个 SKU 有多少能在 文件/易之来灯具 里找到对应高清图文件夹（图源覆盖率）。"""
import sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.generate.zapi_client import ROOT

IMG_EXT = {".png", ".jpg", ".jpeg", ".jfif", ".webp"}
data_root = ROOT / "商品数据"
src_root = ROOT / "文件" / "易之来灯具"


def norm(name: str) -> str:
    """归一化型号：只去"变体副本"后缀(_2 / 空格2 / (2))，保留型号自带数字；再去空格/下划线/连字符、大写。"""
    n = name.strip().upper()
    n = re.sub(r"[ _]\d+$", "", n)       # 去尾部变体标记 "_2" 或 " 2"（前面必须有空格/下划线）
    n = re.sub(r"\s*\(\d+\)$", "", n)    # 去尾部 "(2)"
    n = n.replace(" ", "").replace("_", "").replace("-", "")
    return n


# 1) 收集所有 SKU（商品数据 里的叶子文件夹，排除"不上传"）
skus = []
for cat in data_root.iterdir():
    if not cat.is_dir() or cat.name == "不上传":
        continue
    for prod in cat.iterdir():
        if prod.is_dir():
            skus.append(prod.name)

# 2) 收集 文件/易之来灯具 下所有"含图"文件夹，按归一化名建索引
src_index = {}
for d in src_root.rglob("*"):
    if d.is_dir():
        has_img = any(f.suffix.lower() in IMG_EXT for f in d.iterdir() if f.is_file())
        if has_img:
            src_index.setdefault(norm(d.name), []).append(d)

# 3) 匹配
matched, unmatched = [], []
for sku in skus:
    hits = src_index.get(norm(sku))
    (matched if hits else unmatched).append(sku)

print(f"SKU 总数(可上传): {len(skus)}")
print(f"含图源文件夹(易之来灯具下): {sum(len(v) for v in src_index.values())} 个, 去重型号 {len(src_index)}")
print(f"能匹配到高清图源的 SKU: {len(matched)}  ({len(matched)/len(skus)*100:.0f}%)")
print(f"匹配不到的 SKU: {len(unmatched)}  ({len(unmatched)/len(skus)*100:.0f}%)")
print("\n匹配不到的前 40 个示例：")
for s in unmatched[:40]:
    print("  ", s)
