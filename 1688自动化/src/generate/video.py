# -*- coding: utf-8 -*-
"""M1 · 主视频（i2v：用已生成的主图当首帧，grok 生成 5s 主图视频）。

保真优先：运动 prompt 强调"产品外形/结构完全不变，只做点亮/光晕/轻微镜头运动"，
避免 grok 在视频里改产品。规格见 docs/主图规范.md / specs.py。
"""
from pathlib import Path

from .specs import MAIN_VIDEO
from .zapi_client import ZapiClient

# 首帧优先级：场景图更适合做动态主图视频，其次白底
_FIRST_FRAME_PREFERENCE = ["main_3_scene.jpg", "main_4_scene.jpg",
                           "main_1_white.jpg", "main_2_detail.jpg", "main_5_white_last.jpg"]

MOTION_PROMPT = (
    "以这张图为首帧，保持灯具产品的外形、结构、颜色、比例完全不变，禁止改变产品任何造型；"
    "灯泡由暗到亮缓缓点亮，暖光轻轻呼吸般明灭，光晕自然扩散，"
    "镜头极缓慢地轻微推进或环绕，画面稳定高级，无任何文字、logo、水印"
)


def pick_first_frame(product_out_dir) -> Path:
    """从商品的主图产出里挑一张作视频首帧。"""
    product_out_dir = Path(product_out_dir)
    for name in _FIRST_FRAME_PREFERENCE:
        p = product_out_dir / name
        if p.exists():
            return p
    raise FileNotFoundError(f"{product_out_dir} 下没有可用作首帧的主图")


def make_product_video(product_out_dir, out_path=None, client: ZapiClient = None,
                       first_frame=None, seconds: int = None) -> Path:
    """给一个商品生成主视频。first_frame 不给则自动从其主图产出里挑。"""
    product_out_dir = Path(product_out_dir)
    out_path = Path(out_path) if out_path else product_out_dir / "main_video.mp4"
    seconds = seconds or MAIN_VIDEO["min_seconds"]
    client = client or ZapiClient()
    ff = Path(first_frame) if first_frame else pick_first_frame(product_out_dir)

    return client.gen_video(
        MOTION_PROMPT, out_path,
        first_frame=ff,
        seconds=seconds,
        aspect_ratio="1:1",   # 主图视频跟随 1:1 方图主图
        max_wait=600,
    )
