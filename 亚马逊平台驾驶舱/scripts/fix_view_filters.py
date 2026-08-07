"""Try alternate filter value formats for level/status single-select."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.clients.feishu import FeishuClient, FeishuError
from app.config import get_settings


def main() -> None:
    s = get_settings()
    app = s.feishu_bitable_app_token
    table = s.feishu_table_tasks
    with FeishuClient(s) as client:
        fields = {f["field_name"]: f for f in client.list_fields(app, table)}
        level = fields["等级"]
        print("level field meta:", json.dumps(level, ensure_ascii=False)[:800])
        views = client._api("GET", f"/bitable/v1/apps/{app}/tables/{table}/views")
        items = (views.get("data") or {}).get("items") or []
        red = next(v for v in items if v.get("view_name") == "01_红色任务")
        vid = red["view_id"]
        fid = level["field_id"]
        candidates = [
            '["red"]',
            '"red"',
            "red",
            '["红"]',
            json.dumps(["red"], ensure_ascii=False),
        ]
        # options from property
        opts = ((level.get("property") or {}).get("options")) or []
        print("options", opts)
        for o in opts:
            if o.get("name") == "red" and o.get("id"):
                candidates.append(json.dumps([o["id"]], ensure_ascii=False))
                candidates.append(o["id"])

        for val in candidates:
            body = {
                "property": {
                    "filter_info": {
                        "conjunction": "and",
                        "conditions": [
                            {"field_id": fid, "operator": "is", "value": val}
                        ],
                    }
                }
            }
            try:
                client._api(
                    "PATCH",
                    f"/bitable/v1/apps/{app}/tables/{table}/views/{vid}",
                    json_body=body,
                )
                print("OK value=", val)
                # also apply orange
                orange_view = next(
                    v for v in items if v.get("view_name") == "02_橙色任务"
                )
                body2 = {
                    "property": {
                        "filter_info": {
                            "conjunction": "and",
                            "conditions": [
                                {
                                    "field_id": fid,
                                    "operator": "is",
                                    "value": val.replace("red", "orange")
                                    if isinstance(val, str)
                                    else val,
                                }
                            ],
                        }
                    }
                }
                # better map orange option id
                oval = val
                if opts:
                    rid = next((x.get("id") for x in opts if x.get("name") == "red"), None)
                    oid = next(
                        (x.get("id") for x in opts if x.get("name") == "orange"), None
                    )
                    if rid and oid and rid in str(val):
                        oval = str(val).replace(rid, oid)
                    elif "red" in str(val):
                        oval = str(val).replace("red", "orange")
                body2["property"]["filter_info"]["conditions"][0]["value"] = oval
                client._api(
                    "PATCH",
                    f"/bitable/v1/apps/{app}/tables/{table}/views/{orange_view['view_id']}",
                    json_body=body2,
                )
                print("OK orange value=", oval)
                return
            except FeishuError as e:
                print("fail", val, e.code, e.message[:120])


if __name__ == "__main__":
    main()
