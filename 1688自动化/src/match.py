# -*- coding: utf-8 -*-
"""图源解析：为一个 SKU 找到"身份确证"的白底产品图源。

策略（见记忆 source-folders-are-variant-collections）：
  源文件夹是变体合集，干净白底图无标签。
  1) OCR 海报 -> 找该 SKU 的"单型号带标签海报"作身份锚点(ref)。
  2) 视觉配对(逐项特征,宁严勿松)：把无标签干净图和 ref 比 -> 同款则用干净图(最高保真+身份对)。
  3) 兜底：ref 海报里裁/清出产品 -> grok 去文字去场景铺白(身份由标签背书)。
返回 {"method","image",...}；method: clean_match / poster_clean / none。
"""
from pathlib import Path

from .catalog import norm, IMG_EXT
from .generate.image import is_clean_white_bg, make_main_image
from .generate.zapi_client import ZapiClient

_MATCH_PROMPT = (
    "两张都是同系列灯具产品图（可能是灯泡、台灯、吊灯等）。请逐项比较它们的判别性细节："
    "①整体外形与轮廓（球形/椭圆/圆柱/蘑菇形/锥形…）"
    "②发光结构或灯丝的形状（若是灯丝灯：双环交叉椭圆/圆形螺旋/横向笼状 等；若是灯具：灯罩造型、支架/底座结构）"
    "③材质与颜色（玻璃/金属/布艺、琥珀/烟灰/白 等）。"
    "先分别描述两图这三项，再判定是否为完全同一款产品。宁严勿松：只要有一项明显不同就判 DIFFERENT。"
    "最后一行只输出一个词：SAME 或 DIFFERENT。"
)

_POSTER_CLEAN_PROMPT = (
    "严格保持画面主体灯具产品的外形、灯丝/发光结构、颜色、材质、比例完全一致，禁止改变产品任何细节；"
    "去掉画面里所有文字、型号、参数表、图标、logo、以及背景场景，"
    "只保留该产品居中放在纯白色#FFFFFF背景上，1:1正方形，高清电商主图。"
)


def _code_matches_sku(code: str, sku: str) -> bool:
    a, b = norm(code), norm(sku)
    return a == b or a in b or b in a


def _classify_images(src_dir: Path):
    cleans, posters = [], []
    for f in sorted(src_dir.iterdir()):
        if not (f.is_file() and f.suffix.lower() in IMG_EXT):
            continue
        try:
            (cleans if is_clean_white_bg(f) else posters).append(f)
        except Exception:
            pass
    return cleans, posters


def find_reference_posters(sku, posters, client: ZapiClient, stop_at_first: bool = True):
    """返回"只含该 SKU 单一型号"的带标签海报(排除多型号全家福)。
    stop_at_first=True: 找到第一张即返回(提速，避免 OCR 完整个文件夹)。"""
    refs = []
    for p in posters:
        try:
            codes = client.ocr_model_codes(p)
        except Exception:
            continue
        if len(codes) == 1 and _code_matches_sku(codes[0], sku):
            refs.append(p)
            if stop_at_first:
                break
    return refs


def same_product(clean_img, ref_img, client: ZapiClient) -> bool:
    txt = client.vision_compare(clean_img, ref_img, _MATCH_PROMPT)
    last = [ln for ln in txt.strip().splitlines() if ln.strip()]
    tail = (last[-1] if last else "").upper()
    return "SAME" in tail and "DIFFERENT" not in tail


def resolve_source(sku, src_dir, out_dir, client: ZapiClient = None) -> dict:
    src_dir, out_dir = Path(src_dir), Path(out_dir)
    client = client or ZapiClient()
    cleans, posters = _classify_images(src_dir)
    refs = find_reference_posters(sku, posters, client)

    # 无身份锚点 -> 无法确证，交人工
    if not refs:
        return {"sku": sku, "method": "none", "reason": "无该SKU单型号带标签海报作锚点",
                "cleans": len(cleans), "posters": len(posters)}

    # 1) 视觉配对：找和 ref 同款的干净图
    for c in cleans:
        for rp in refs:
            try:
                if same_product(c, rp, client):
                    img = make_main_image(c, out_dir / "source_main.jpg")
                    return {"sku": sku, "method": "clean_match", "image": str(img),
                            "clean": c.name, "ref": rp.name}
            except Exception:
                continue

    # 2) 兜底：清 ref 海报出白底产品（身份由标签背书）
    rp = refs[0]
    try:
        raw = client.edit_image(rp, _POSTER_CLEAN_PROMPT, out_dir / "_poster_clean_raw.jpg")
        img = make_main_image(raw, out_dir / "source_main.jpg")
        Path(raw).unlink(missing_ok=True)
        return {"sku": sku, "method": "poster_clean", "image": str(img), "ref": rp.name}
    except Exception as e:
        return {"sku": sku, "method": "none", "reason": f"兜底清海报失败: {type(e).__name__}: {e}",
                "ref": rp.name}
