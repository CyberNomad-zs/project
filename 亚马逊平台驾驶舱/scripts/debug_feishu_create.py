import json
import httpx
from app.config import get_settings

s = get_settings()
r = httpx.post(
    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
    json={"app_id": s.feishu_app_id, "app_secret": s.feishu_app_secret},
    timeout=30,
)
print("token", r.status_code, r.text[:300])
tok = r.json()["tenant_access_token"]
headers = {
    "Authorization": f"Bearer {tok}",
    "Content-Type": "application/json; charset=utf-8",
}
r2 = httpx.post(
    "https://open.feishu.cn/open-apis/bitable/v1/apps",
    headers=headers,
    json={"name": "ASIN健康度监控"},
    timeout=30,
)
print("create", r2.status_code)
print(r2.text)

# also try list app scopes-ish: drive root meta
r3 = httpx.get(
    "https://open.feishu.cn/open-apis/drive/v1/files",
    headers=headers,
    params={"page_size": 5},
    timeout=30,
)
print("drive files", r3.status_code, r3.text[:500])
