#!/usr/bin/env bash
set -euo pipefail
ENV=/opt/qingquan/.env
# restore working Base + table that already has 5 records
sudo sed -i 's|^FEISHU_BITABLE_APP_TOKEN_TK=.*|FEISHU_BITABLE_APP_TOKEN_TK=C1iHbw6TVad6rUsbZnbc2gSDnHg|' "$ENV"
sudo sed -i 's|^FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=.*|FEISHU_BITABLE_TABLE_TK_EXPERIENCE_DAILY=tbl9CYd8vb4DJaGN|' "$ENV"
grep -E '^FEISHU_BITABLE_APP_TOKEN_TK=|^FEISHU_BITABLE_TABLE_TK_EXPERIENCE' "$ENV"

docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
  "DELETE FROM public.sync_feishu_map WHERE table_key = 'tk_experience_daily';"

docker restart qingquan-api-1
sleep 12
curl -sS -m 8 http://127.0.0.1:8000/health; echo
docker cp /tmp/bitable.py qingquan-api-1:/app/app/adapters/feishu/bitable.py
docker cp /tmp/tk_feishu_sync.py qingquan-api-1:/app/app/jobs/tk_feishu_sync.py
docker cp /tmp/config.py qingquan-api-1:/app/app/config.py
docker cp /tmp/_prod_run_exp_sync.py qingquan-api-1:/tmp/run_exp_sync.py

docker exec -e PYTHONPATH=/app -w /app qingquan-api-1 python /tmp/run_exp_sync.py

docker exec qingquan-db-1 psql -U qingquan -d qingquan -c \
  "SELECT table_key, table_id, count(*) FROM public.sync_feishu_map WHERE table_key='tk_experience_daily' GROUP BY 1,2;"

set -a; . /opt/qingquan/.env; set +a
docker exec -e FEISHU_APP_ID -e FEISHU_APP_SECRET -e FEISHU_BITABLE_APP_TOKEN_TK \
  -w /app qingquan-api-1 python - <<'PY'
import json, os, urllib.request
app_id=os.environ['FEISHU_APP_ID']; secret=os.environ['FEISHU_APP_SECRET']
app_token=os.environ['FEISHU_BITABLE_APP_TOKEN_TK']
def req(m,u,b=None,t=None):
  import json as J
  h={'Content-Type':'application/json'}
  if t: h['Authorization']=f'Bearer {t}'
  d=None if b is None else J.dumps(b).encode()
  r=urllib.request.Request(u,data=d,headers=h,method=m)
  with urllib.request.urlopen(r,timeout=60) as resp:
    return J.loads(resp.read().decode())
tok=req('POST','https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',{'app_id':app_id,'app_secret':secret})
token=tok['tenant_access_token']
tid='tbl9CYd8vb4DJaGN'
rec=req('GET',f'https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{tid}/records?page_size=10',t=token)
print('total', (rec.get('data') or {}).get('total'), 'code', rec.get('code'))
for it in (rec.get('data') or {}).get('items') or []:
  f=it.get('fields') or {}
  print(f.get('店铺'), f.get('店铺ID'), f.get('体验总分'), f.get('日期') or f.get('业务日'))
print('OPEN_URL', f'https://feishu.cn/base/{app_token}?table={tid}')
PY
echo RESTORE_DONE
