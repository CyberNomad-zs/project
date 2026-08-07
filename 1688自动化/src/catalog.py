# -*- coding: utf-8 -*-
"""商品清单 ↔ 图源 的匹配（把 商品数据 的 SKU 映射到 文件/易之来灯具 下的高清图文件夹）。"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "商品数据"
SRC_ROOT = ROOT / "文件" / "易之来灯具"
IMG_EXT = {".png", ".jpg", ".jpeg", ".jfif", ".webp"}


def norm(name: str) -> str:
    """归一化型号：只去变体副本后缀(_2/空格2/(2))，保留型号自带数字；再去空格/下划线/连字符、大写。"""
    n = name.strip().upper()
    n = re.sub(r"[ _]\d+$", "", n)
    n = re.sub(r"\s*\(\d+\)$", "", n)
    return n.replace(" ", "").replace("_", "").replace("-", "")


def list_skus():
    """返回 [(sku, category)]，排除'不上传'。"""
    out = []
    for cat in sorted(DATA_ROOT.iterdir()):
        if not cat.is_dir() or cat.name == "不上传":
            continue
        for prod in sorted(cat.iterdir()):
            if prod.is_dir():
                out.append((prod.name, cat.name))
    return out


def build_source_index():
    """{归一化型号: [含图文件夹...]}，扫描 文件/易之来灯具 全树。"""
    idx = {}
    for d in SRC_ROOT.rglob("*"):
        if d.is_dir() and any(f.suffix.lower() in IMG_EXT for f in d.iterdir() if f.is_file()):
            idx.setdefault(norm(d.name), []).append(d)
    return idx


def matched_skus():
    """返回有高清图源的 SKU：[(sku, category, source_dir)]。同名多个源取图最多的。"""
    idx = build_source_index()
    out = []
    for sku, cat in list_skus():
        hits = idx.get(norm(sku))
        if hits:
            best = max(hits, key=lambda d: sum(
                1 for f in d.iterdir() if f.is_file() and f.suffix.lower() in IMG_EXT))
            out.append((sku, cat, best))
    return out
