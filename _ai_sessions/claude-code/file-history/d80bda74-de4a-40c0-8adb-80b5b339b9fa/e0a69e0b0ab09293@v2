# -*- coding: utf-8 -*-
import json
import httpx
from app.config import get_settings

APP = "TkW0bXEAAa3Fo3sdKagcL9fTn2b"
TABLE = "tblAj6hIX4qinZGE"


def main() -> None:
    s = get_settings()
    print("app_id", s.feishu_app_id)
    r = httpx.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": s.feishu_app_id, "app_secret": s.feishu_app_secret},
        timeout=30,
    )
    print("token", r.status_code, r.json().get("code"), r.json().get("msg"))
    tok = r.json()["tenant_access_token"]
    h = {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json; charset=utf-8",
    }

    checks = []

    def get(path, label):
        resp = httpx.get(
            "https://open.feishu.cn/open-apis" + path, headers=h, timeout=30
        )
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text[:300]}
        print("=" * 50)
        print(label, resp.status_code, data.get("code"), (data.get("msg") or "")[:120])
        if data.get("code") == 0:
            print(json.dumps(data.get("data"), ensure_ascii=False)[:800])
        return data

    def post(path, body, label):
        resp = httpx.post(
            "https://open.feishu.cn/open-apis" + path,
            headers=h,
            json=body,
            timeout=30,
        )
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text[:300]}
        print("=" * 50)
        print(label, resp.status_code, data.get("code"), (data.get("msg") or "")[:200])
        if data.get("code") == 0:
            print(json.dumps(data.get("data"), ensure_ascii=False)[:800])
        else:
            print(json.dumps(data, ensure_ascii=False)[:800])
        return data

    get(f"/bitable/v1/apps/{APP}", "app meta")
    get(f"/bitable/v1/apps/{APP}/tables", "tables")
    get(f"/drive/v1/permissions/{APP}/members?type=bitable", "members")
    # create field on default table
    post(
        f"/bitable/v1/apps/{APP}/tables/{TABLE}/fields",
        {"field_name": "API测试字段", "type": 1},
        "create field",
    )
    # create record
    post(
        f"/bitable/v1/apps/{APP}/tables/{TABLE}/records",
        {"fields": {"文本": "write-test"}},
        "create record",
    )
    # create table minimal
    post(
        f"/bitable/v1/apps/{APP}/tables",
        {
            "table": {
                "name": "测试子表",
                "default_view_name": "默认",
                "fields": [{"field_name": "主键", "type": 1}],
            }
        },
        "create table",
    )
    # old base still writable?
    old = "FrXvbTodVad1Kqs0hCkckrI8noc"
    get(f"/bitable/v1/apps/{old}", "OLD app meta")
    post(
        f"/bitable/v1/apps/{old}/tables",
        {
            "table": {
                "name": "_perm_probe_delete_me",
                "default_view_name": "默认",
                "fields": [{"field_name": "主键", "type": 1}],
            }
        },
        "create table on OLD base",
    )


if __name__ == "__main__":
    main()
