# -*- coding: utf-8 -*-
"""跨品类多样 SKU 的图源解析压测。"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.match import resolve_source
from src.catalog import matched_skus
from src.generate.zapi_client import ZapiClient, ROOT

SAMPLE = ["FT3D076", "LT-1317", "LT-1434", "ONE-DS125150MWFG", "VI-GO90112A"]
index = {sku: (cat, src) for sku, cat, src in matched_skus()}
client = ZapiClient()
out_root = ROOT / "output" / "_resolve_sample"
results = []
for sku in SAMPLE:
    cat, src = index[sku]
    t0 = time.time()
    r = resolve_source(sku, src, out_root / sku, client)
    r["seconds"] = round(time.time() - t0, 1)
    results.append(r)
    print(f"{sku:<20} method={r['method']:<12} ({r['seconds']}s) "
          f"{ {k:v for k,v in r.items() if k in ('clean','ref','reason')} }", flush=True)

(out_root / "sample_report.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("\n报告:", out_root / "sample_report.json")
