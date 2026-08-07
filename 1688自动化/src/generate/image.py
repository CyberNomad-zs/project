# -*- coding: utf-8 -*-
"""
M1 · 主图归一化（精确还原真实产品，非生成式）。

策略（见记忆 main-image-fidelity-decision）：
  真实产品像素分毫不动 -> 提纯近白背景为纯白 -> 裁到产品外框 ->
  居中铺到正方形白底画布(产品占比 50%~75%) -> 缩放到目标尺寸 -> 控制文件大小。

只处理"类型A：干净白底产品图"。类型B（带文字/场景的卖点海报）应先被
`is_clean_white_bg()` 挡掉，归到卖点/详情用途，不进主图。
"""

from pathlib import Path

import numpy as np
from PIL import Image

from .specs import MAIN_IMAGE, WHITE_BG_RGB, WHITE_TOLERANCE

IMG_EXT = {".png", ".jpg", ".jpeg", ".jfif", ".webp"}

# grok 场景/卖点图 prompt：统一的强制保真前缀 + 两个不同场景
_FIDELITY_PREFIX = (
    "严格保持这个灯具产品的外形轮廓、玻璃/外壳形状、颜色质感、"
    "内部灯丝或发光结构、金属灯头与整体比例与原图完全一致，"
    "禁止改变产品任何造型和细节；"
)
SCENE_PROMPTS = [
    _FIDELITY_PREFIX + "将其点亮，安放在温馨复古的室内场景中（木质边桌、暖色氛围、"
    "虚化背景的客厅），营造家居氛围感，电商卖点主图，1:1正方形，画面无任何文字、logo、水印",
    _FIDELITY_PREFIX + "将其点亮，置于简约现代的桌面场景（浅色背景、柔和影棚光、"
    "少量绿植点缀、干净留白），突出高级质感，电商卖点主图，1:1正方形，画面无任何文字、logo、水印",
]


def _to_rgb(src) -> Image.Image:
    img = Image.open(src)
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, WHITE_BG_RGB)
        img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def _near_white_mask(arr: np.ndarray, tol: int) -> np.ndarray:
    """True = 近白像素（背景）。arr: HxWx3 uint8。"""
    return np.all(arr >= (255 - tol), axis=-1)


def is_clean_white_bg(src, border_frac: float = 0.06, tol: int = 25,
                      min_white_ratio: float = 0.90) -> bool:
    """判断是否"干净白底产品图"（类型A）：看四周边框区域是否基本纯白。
    带场景/文字的卖点海报(类型B)边框不白 -> 返回 False。"""
    arr = np.asarray(_to_rgb(src))
    h, w = arr.shape[:2]
    bw = max(1, int(min(h, w) * border_frac))
    border = np.concatenate([
        arr[:bw, :, :].reshape(-1, 3), arr[-bw:, :, :].reshape(-1, 3),
        arr[:, :bw, :].reshape(-1, 3), arr[:, -bw:, :].reshape(-1, 3),
    ])
    white_ratio = _near_white_mask(border, tol).mean()
    return white_ratio >= min_white_ratio


def _product_bbox(arr: np.ndarray, tol: int):
    """产品外接框（非白像素的范围）。返回 (left, top, right, bottom) 或 None。"""
    fg = ~_near_white_mask(arr, tol)
    ys, xs = np.where(fg)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def make_main_image(src, out_path,
                    target_size=None, product_ratio: float = 0.72,
                    purify_tol: int = None, quality: int = 90) -> Path:
    """把一张干净白底产品图归一化为合规主图。产品像素不改，只提纯背景+裁切居中+缩放。"""
    target_size = target_size or MAIN_IMAGE["size_default"]
    purify_tol = WHITE_TOLERANCE if purify_tol is None else purify_tol
    tw, th = target_size

    arr = np.asarray(_to_rgb(src)).copy()

    # 1) 提纯：近白 -> 纯白 255（背景干净，产品本体像素不受影响）
    arr[_near_white_mask(arr, purify_tol)] = WHITE_BG_RGB

    # 2) 产品外接框（用宽松容差找产品，避免把浅色产品边缘当背景切掉）
    bbox = _product_bbox(arr, tol=max(purify_tol, 20))
    if bbox is None:
        raise ValueError(f"未找到产品主体（可能整图接近纯白）：{src}")
    l, t, r, b = bbox
    product = Image.fromarray(arr[t:b, l:r])

    # 3) 缩放：让产品长边占画布 product_ratio
    pw, ph = product.size
    target_long = int(min(tw, th) * product_ratio)
    scale = target_long / max(pw, ph)
    new_size = (max(1, round(pw * scale)), max(1, round(ph * scale)))
    product = product.resize(new_size, Image.LANCZOS)

    # 4) 居中铺到纯白正方形画布
    canvas = Image.new("RGB", target_size, WHITE_BG_RGB)
    ox = (tw - new_size[0]) // 2
    oy = (th - new_size[1]) // 2
    canvas.paste(product, (ox, oy))

    # 5) 存盘并控制文件大小 <= 500KB
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _save_capped(canvas, out_path, MAIN_IMAGE["max_bytes"], quality)
    return out_path


def _save_capped(img: Image.Image, out_path: Path, max_bytes: int, quality: int):
    """JPG 存盘，若超过 max_bytes 则逐步降质量。"""
    if out_path.suffix.lower() in (".jpg", ".jpeg"):
        q = quality
        while q >= 60:
            img.save(out_path, "JPEG", quality=q, optimize=True)
            if out_path.stat().st_size <= max_bytes:
                return
            q -= 8
        return
    img.save(out_path, optimize=True)


def normalize_generated(src, out_path, target_size=None, quality: int = 90) -> Path:
    """把 grok 生成的场景图规范化：转正方形目标尺寸 + 控制文件大小。产品由 prompt 保真，此处不改画面。"""
    target_size = target_size or MAIN_IMAGE["size_default"]
    img = _to_rgb(src)
    if img.size != tuple(target_size):
        # grok 通常已是 1:1；若非正方形，居中裁成正方形再缩放
        w, h = img.size
        if w != h:
            s = min(w, h)
            img = img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
        img = img.resize(target_size, Image.LANCZOS)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _save_capped(img, out_path, MAIN_IMAGE["max_bytes"], quality)
    return out_path


def pick_best_clean_shot(product_dir):
    """从型号目录里挑最合适的干净白底图：产品外框面积最大者（主体大、可裁切空间足）。"""
    product_dir = Path(product_dir)
    best, best_area = None, -1
    for f in sorted(product_dir.iterdir()):
        if f.suffix.lower() not in IMG_EXT or not f.is_file():
            continue
        try:
            if not is_clean_white_bg(f):
                continue
            arr = np.asarray(_to_rgb(f))
            bbox = _product_bbox(arr, tol=20)
            if bbox is None:
                continue
            l, t, r, b = bbox
            area = (r - l) * (b - t)
            if area > best_area:
                best, best_area = f, area
        except Exception:
            continue
    return best


def make_product_mains(product_dir, out_dir, client=None, do_scene: bool = True,
                       clean_source=None) -> dict:
    """一个商品 -> 5 张主图：2白底(非生成) + 2场景(grok) + 1纯白底(强制)。
    clean_source 给定则用它作图源(身份确证版)；否则从 product_dir 盲选。
    返回 {slot: path/None}。缺干净图源时白底相关槽为 None。"""
    out_dir = Path(out_dir)
    result = {}
    clean = Path(clean_source) if clean_source else pick_best_clean_shot(product_dir)

    if clean is not None:
        # 同一张真实照片的不同构图，都是真实像素 -> 保真
        result["main_1_white"] = make_main_image(clean, out_dir / "main_1_white.jpg", product_ratio=0.68)
        result["main_2_detail"] = make_main_image(clean, out_dir / "main_2_detail.jpg", product_ratio=0.85)
        result["main_5_white_last"] = make_main_image(clean, out_dir / "main_5_white_last.jpg", product_ratio=0.75)
    else:
        result["main_1_white"] = result["main_2_detail"] = result["main_5_white_last"] = None

    if do_scene and clean is not None:
        if client is None:
            from .zapi_client import ZapiClient
            client = ZapiClient()
        for i, prompt in enumerate(SCENE_PROMPTS, start=3):
            key = f"main_{i}_scene"
            try:
                raw = client.edit_image(clean, prompt, out_dir / f"_{key}_raw.jpg")
                result[key] = normalize_generated(raw, out_dir / f"{key}.jpg")
                Path(raw).unlink(missing_ok=True)
            except Exception as e:
                result[key] = None
                print(f"    [{key}] 场景生成失败: {type(e).__name__}: {e}")
    else:
        result["main_3_scene"] = result["main_4_scene"] = None

    return result
