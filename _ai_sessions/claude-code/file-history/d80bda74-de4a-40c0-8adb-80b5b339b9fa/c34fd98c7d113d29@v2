"""Export open anomaly tasks for business review (CSV + summary)."""
from __future__ import annotations

import csv
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
db = ROOT / "data" / "bridge.db"
out_dir = ROOT / "data" / "exports"
out_dir.mkdir(parents=True, exist_ok=True)

c = sqlite3.connect(db)
c.row_factory = sqlite3.Row
rows = c.execute(
    """
    SELECT task_id, biz_date, shop_name, asin, product_title, anomaly_type, level,
           current_value, baseline_value, change_value, owner, reviewer, status,
           due_at, streak, need_boss, payload_json
    FROM anomaly_tasks
    WHERE status NOT IN ('closed','resolved')
    ORDER BY level DESC, anomaly_type, shop_name, asin
    """
).fetchall()

csv_path = out_dir / "open_tasks_review.csv"
with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(
        [
            "task_id",
            "biz_date",
            "shop_name",
            "asin",
            "product_title",
            "anomaly_type",
            "level",
            "current_value",
            "baseline_value",
            "change_value",
            "owner",
            "reviewer",
            "status",
            "due_at",
            "streak",
            "need_boss",
            "建议处理",
        ]
    )
    for r in rows:
        tip = {
            "inventory_low": "核可售/在途/补货；确认是否真断货",
            "inventory_high": "核库龄与动销；考虑促销/调拨/清货",
            "acos_abnormal": "核广告结构与出价；是否活动期",
            "review_abnormal": "看差评内容；是否需客服/Listing",
            "sales_drop": "核流量/广告/竞品/库存",
            "ad_spend_abnormal": "核花费与广告产出是否匹配",
        }.get(r["anomaly_type"], "核实是否属实并填动作表")
        w.writerow(
            [
                r["task_id"],
                r["biz_date"],
                r["shop_name"],
                r["asin"],
                r["product_title"],
                r["anomaly_type"],
                r["level"],
                r["current_value"],
                r["baseline_value"],
                r["change_value"],
                r["owner"],
                r["reviewer"],
                r["status"],
                r["due_at"],
                r["streak"],
                r["need_boss"],
                tip,
            ]
        )

by_type = Counter((r["anomaly_type"], r["level"]) for r in rows)
by_owner = Counter(r["owner"] or "未分配" for r in rows)
by_shop = Counter(r["shop_name"] for r in rows)

md = []
md.append("# 异常任务业务评审清单")
md.append("")
md.append(f"- 导出时间业务日以任务 `biz_date` 为准")
md.append(f"- 未关闭任务合计：**{len(rows)}**")
md.append(f"- 明细 CSV：`data/exports/open_tasks_review.csv`")
md.append("")
md.append("## 按类型×等级")
md.append("")
md.append("| 类型 | 等级 | 数量 |")
md.append("|---|---|---:|")
for (t, lv), n in sorted(by_type.items(), key=lambda x: (-x[1], x[0][0], x[0][1])):
    md.append(f"| {t} | {lv} | {n} |")
md.append("")
md.append("## 按负责人")
md.append("")
for o, n in by_owner.most_common():
    md.append(f"- {o}: {n}")
md.append("")
md.append("## 按店铺")
md.append("")
for s, n in by_shop.most_common():
    md.append(f"- {s}: {n}")
md.append("")
md.append("## 建议业务过会问题")
md.append("")
md.append("1. `inventory_low` 红是否都是真断货/即将断货？有没有在途未算进来的？")
md.append("2. `inventory_high` 橙是否要再收紧（例如可售天数>240 或仅 S/A）？")
md.append("3. `acos_abnormal` 默认目标 30% 是否按店铺/品类拆分？")
md.append("4. 哪些 ASIN 应标 S/A 核心款？")
md.append("5. 动作表里「需要老板决策」的标准是什么？")
md.append("")
md.append("## 红任务明细（优先过）")
md.append("")
md.append("| 负责人 | 店铺 | ASIN | 类型 | 当前值 | 产品 |")
md.append("|---|---|---|---|---:|---|")
for r in rows:
    if r["level"] != "red":
        continue
    title = (r["product_title"] or "")[:40]
    md.append(
        f"| {r['owner'] or ''} | {r['shop_name']} | {r['asin']} | {r['anomaly_type']} | {r['current_value']} | {title} |"
    )

md_path = out_dir / "open_tasks_review.md"
md_path.write_text("\n".join(md), encoding="utf-8")
print(f"rows={len(rows)}")
print(f"csv={csv_path}")
print(f"md={md_path}")
for (t, lv), n in sorted(by_type.items(), key=lambda x: (-x[1], x[0][0])):
    print(f"  {t}/{lv}: {n}")
