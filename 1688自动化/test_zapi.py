# -*- coding: utf-8 -*-
"""
zapi / grok 连通性冒烟测试（第一步验证）。

用法：
    python test_zapi.py                # 用默认样例图
    python test_zapi.py 某张图片路径     # 指定输入图做图生图

会做两件事：
  1) 文生图：证明 key + 网关 + grok 模型能通（最少变量）。
  2) 图生图：项目主用路径，拿一张真实产品图 + prompt 生成一张电商主图。
产物落在 output/_smoke/ 下，请人眼评审是否达电商上架审美/合规。
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.generate.zapi_client import ZapiClient, ROOT

OUT_DIR = ROOT / "output" / "_smoke"


def pick_sample_image() -> Path:
    """优先用真实产品图集里的第一张，退而用商品数据里的第一张。"""
    candidates = [
        ROOT / "文件" / "易之来灯具" / "A60OFA",
        ROOT / "商品数据",
    ]
    for base in candidates:
        if base.exists():
            for f in sorted(base.rglob("*.png")):
                return f
            for f in sorted(base.rglob("*.jpg")):
                return f
    raise FileNotFoundError("没找到任何样例图片")


def kb(path: Path) -> str:
    return f"{path.stat().st_size / 1024:.0f} KB"


def main():
    client = ZapiClient()
    print(f"网关: {client.base_url}")
    print(f"主图模型: {client.models.get('image_main')}")
    print(f"输出目录: {OUT_DIR}\n")

    # ---- 1) 文生图 ----
    print("[1/2] 文生图 (text->image) ...")
    t0 = time.time()
    try:
        out1 = client.gen_image(
            prompt="一盏现代简约风格的 LED 灯泡产品，纯白背景，电商主图，居中，高清，柔和影棚光",
            out_path=OUT_DIR / "gen.png",
        )
        print(f"    OK  {out1}  ({kb(out1)}, {time.time()-t0:.1f}s)")
    except Exception as e:
        print(f"    失败: {type(e).__name__}: {e}")

    # ---- 2) 图生图 ----
    sample = Path(sys.argv[1]) if len(sys.argv) > 1 else pick_sample_image()
    print(f"\n[2/2] 图生图 (image->image)  输入: {sample.name} ...")
    t0 = time.time()
    try:
        out2 = client.edit_image(
            image_paths=sample,
            prompt="把这张灯具产品图做成 1688 电商主图：纯白背景，产品居中，去杂物，"
                   "光线明亮均匀，突出质感，1:1 方图，无多余文字",
            out_path=OUT_DIR / "edit.png",
        )
        print(f"    OK  {out2}  ({kb(out2)}, {time.time()-t0:.1f}s)")
    except Exception as e:
        print(f"    失败: {type(e).__name__}: {e}")

    print("\n完成。请打开 output/_smoke/ 目录人眼评审生成质量。")


if __name__ == "__main__":
    main()
