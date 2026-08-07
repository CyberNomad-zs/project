# -*- coding: utf-8 -*-
"""M4 第一步：验证 1688 登录 cookie 是否还有效。"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.publish.session import check_login, ROOT

shot = ROOT / "output" / "_m4" / "login_check.png"
r = check_login(shot=shot)
print(json.dumps(r, ensure_ascii=False, indent=2))
print("\n登录态:", "[有效]" if r["logged_in"] else "[失效-需刷新cookie]")
