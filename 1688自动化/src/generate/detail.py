# -*- coding: utf-8 -*-
"""M1 · 详情页（把成品卖点海报/场景/白底产品图，规范成 790px 宽的详情段图）。

关键：详情页允许文字，所以从主图里剔除的"卖点海报"(带型号/参数/品牌文案)正是详情页的最佳素材。
本模块不生成内容，只做"收集 + 规范化拼段"。规格见 specs.py DETAIL(790px宽, 单段≤1500高)。
"""
from pathlib import Path

from PIL import Image

from .specs import DETAIL, WHITE_BG_RGB
from .image import is_clean_white_bg, _to_rgb, IMG_EXT


def _resize_to_width(img: Image.Image, width: int) -> Image.Image:
    if img.width == width:
        return img
    h = round(img.height * width / img.width)
    return img.resize((width, h), Image.LANCZOS)


def _split_tall(img: Image.Image, max_h: int):
    """把过高的图纵向切成 ≤max_h 的若干段。"""
    if img.height <= max_h:
        yield img
        return
    y = 0
    while y < img.height:
        yield img.crop((0, y, img.width, min(y + max_h, img.height)))
        y += max_h


def to_detail_segments(image_paths, out_dir, width: int = None, max_h: int = None,
                       quality: int = 88):
    """把一组图规范成详情段图 detail_01.jpg ...（790宽，超高自动切）。"""
    width = width or DETAIL["pc_width"]
    max_h = max_h or DETAIL["max_height_per_image"]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    outs, idx = [], 1
    for p in image_paths:
        img = _resize_to_width(_to_rgb(p), width)
        for seg in _split_tall(img, max_h):
            # 详情图背景铺白，避免透明/异形
            canvas = Image.new("RGB", seg.size, WHITE_BG_RGB)
            canvas.paste(seg, (0, 0))
            op = out_dir / f"detail_{idx:02d}.jpg"
            canvas.save(op, "JPEG", quality=quality, optimize=True)
            outs.append(op)
            idx += 1
    return outs


def collect_detail_sources(product_src_dir, product_out_dir, max_posters: int = 8):
    """详情素材顺序：干净白底产品图开场 -> 成品卖点海报(参数/品牌/场景) -> 生成的场景图收尾。"""
    src = Path(product_src_dir)
    out = Path(product_out_dir)
    seq = []

    w1 = out / "main_1_white.jpg"
    if w1.exists():
        seq.append(w1)

    posters = [f for f in sorted(src.iterdir())
               if f.is_file() and f.suffix.lower() in IMG_EXT and not is_clean_white_bg(f)]
    seq += posters[:max_posters]

    for name in ("main_4_scene.jpg", "main_3_scene.jpg"):
        p = out / name
        if p.exists():
            seq.append(p)
            break
    return seq


def make_product_detail(product_src_dir, product_out_dir, max_posters: int = 8) -> list:
    """给一个商品生成详情段图，落在 <out>/detail/ 下。返回段图路径列表。"""
    seq = collect_detail_sources(product_src_dir, product_out_dir, max_posters=max_posters)
    return to_detail_segments(seq, Path(product_out_dir) / "detail")
