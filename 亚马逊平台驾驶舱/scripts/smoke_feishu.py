#!/usr/bin/env python3
"""飞书连通性冒烟：token + 列多维表 + 可选写 1 行测试后删除说明。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.clients.feishu import FeishuClient, FeishuError
from app.config import get_settings


def main() -> int:
    s = get_settings()
    if not s.has_feishu:
        print("ERROR: 配置 FEISHU_APP_ID / FEISHU_APP_SECRET")
        return 2
    try:
        with FeishuClient(s) as client:
            token = client.get_tenant_access_token()
            print(f"OK tenant_access_token len={len(token)}")

            app_token = s.feishu_bitable_app_token
            if not app_token:
                print("WARN: 未配置 FEISHU_BITABLE_APP_TOKEN，仅 token 成功")
                print("可运行: python scripts/init_feishu_tables.py")
                return 0

            tables = client.list_tables(app_token)
            print(f"OK bitable tables ({len(tables)}):")
            for t in tables:
                print(f"  - {t.get('name')}: {t.get('table_id')}")

            table_id = s.feishu_table_asin_daily
            if table_id:
                fields = client.list_fields(app_token, table_id)
                names = [f.get("field_name") for f in fields]
                print(f"OK ASIN每日数据 字段数={len(names)}")
                if "主键" not in names:
                    print("WARN: 缺少「主键」字段，upsert 会失败，请用 init 脚本建表")
                # 写一条测试记录
                test_key = "__smoke_test__"
                client.upsert_by_text_key(
                    app_token,
                    table_id,
                    [
                        {
                            "主键": test_key,
                            "日期": "1970-01-01",
                            "店铺": "SMOKE",
                            "ASIN": "SMOKE",
                            "产品名称": "连通性测试，可删",
                        }
                    ],
                    key_field="主键",
                )
                print(f"OK 已 upsert 测试行 主键={test_key}（可在表里删除）")
            else:
                print("WARN: 未配置 FEISHU_TABLE_ASIN_DAILY")

            if s.feishu_bot_webhook:
                client.send_webhook_text("【ASIN健康度】飞书机器人连通性测试 OK")
                print("OK webhook 已发送")
            else:
                print("INFO: 未配置 FEISHU_BOT_WEBHOOK，跳过机器人测试")
            return 0
    except FeishuError as e:
        print(f"FEISHU ERROR [{e.code}] {e.message}")
        print(e.payload)
        return 1
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
