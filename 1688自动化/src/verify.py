# -*- coding: utf-8 -*-
"""图源型号核对层：OCR 源文件夹里海报的型号编码，判定该 SKU 的图源是否可信。

分类：
  coherent       文件夹里读到的型号都属于该 SKU -> 可信，自动图源放行
  mixed_has_self 既有该 SKU 的型号、也有别的型号 -> 混合，需人工挑对应图
  no_self        没读到该 SKU 的型号（只有别的型号）-> 该 SKU 可能根本没图，需人工/补图
  no_label       没读到任何型号 -> 无法核对，需人工
"""
import json
import time
from pathlib import Path

from .catalog import matched_skus, norm, IMG_EXT, ROOT
from .generate.image import is_clean_white_bg
from .generate.zapi_client import ZapiClient

OUT = ROOT / "output" / "verify_report.json"


def _code_matches_sku(code: str, sku: str) -> bool:
    a, b = norm(code), norm(sku)
    return a == b or a in b or b in a


def verify_sku(sku: str, src_dir: Path, client: ZapiClient, max_posters: int = 6) -> dict:
    """OCR 该 SKU 源文件夹里的海报，判定图源可信度。"""
    src_dir = Path(src_dir)
    posters = [f for f in sorted(src_dir.iterdir())
               if f.is_file() and f.suffix.lower() in IMG_EXT and not is_clean_white_bg(f)]
    read = []            # [(文件名, [codes])]
    self_codes, foreign = set(), set()
    for f in posters[:max_posters]:
        try:
            codes = client.ocr_model_codes(f)
        except Exception as e:
            read.append((f.name, f"ERR:{type(e).__name__}"))
            continue
        read.append((f.name, codes))
        for code in codes:
            (self_codes if _code_matches_sku(code, sku) else foreign).add(code)

    if self_codes and not foreign:
        status = "coherent"
    elif self_codes and foreign:
        status = "mixed_has_self"
    elif foreign:
        status = "no_self"
    else:
        status = "no_label"
    return {"sku": sku, "status": status,
            "self_codes": sorted(self_codes), "foreign_codes": sorted(foreign),
            "ocr": [(n, c) for n, c in read]}


def run_verify(limit: int = None, max_posters: int = 6) -> dict:
    skus = matched_skus()
    if limit:
        skus = skus[:limit]
    client = ZapiClient()
    buckets = {"coherent": 0, "mixed_has_self": 0, "no_self": 0, "no_label": 0}
    items = []
    t0 = time.time()
    for i, (sku, cat, src_dir) in enumerate(skus, 1):
        r = verify_sku(sku, src_dir, client, max_posters=max_posters)
        r["category"] = cat
        r["source"] = src_dir.name
        buckets[r["status"]] += 1
        items.append(r)
        print(f"[{i}/{len(skus)}] {sku:<22} {r['status']:<14} "
              f"self={r['self_codes']} foreign={r['foreign_codes']}")
    report = {"total": len(skus), "buckets": buckets,
              "elapsed_seconds": round(time.time() - t0, 1), "items": items}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n核对汇总: 可信{buckets['coherent']} 混合{buckets['mixed_has_self']} "
          f"缺本型号{buckets['no_self']} 无标签{buckets['no_label']} / 共{len(skus)}")
    print(f"报告: {OUT}")
    return report
