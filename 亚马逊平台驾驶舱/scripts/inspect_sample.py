import json
from pathlib import Path

d = json.loads(
    Path("data/snapshots/smoke_sample_2026-07-21.json").read_text(encoding="utf-8")
)
fm = d.get("fieldsMap") or {}
print("fieldsMap keys", len(fm))
interesting = [
    "salePrice",
    "saleNum",
    "orderNum",
    "avgSalePrice",
    "sessions",
    "pageView",
    "conversionRate",
    "buyBoxPercent",
    "adTotalImpression",
    "adClicks",
    "adClickRate",
    "adTotalCost",
    "cpc",
    "acos",
    "available",
    "inTransit",
    "availableDays",
    "invAge365PlusDays",
    "rating",
    "ratingCount",
    "lowReviewNum",
    "reviewNum",
    "sevenSaleNum",
    "adTotalSales",
    "fbaInventory",
]
for k in interesting:
    print(k, "->", fm.get(k))
print("--- all keys ---")
print(", ".join(sorted(fm.keys())))
