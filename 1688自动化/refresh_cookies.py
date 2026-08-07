# -*- coding: utf-8 -*-
"""半自动刷新 1688 登录 cookie。

用法（必须用 M4 环境）:
  .venv-m4\\Scripts\\python.exe refresh_cookies.py

会弹出 Chromium 窗口 → 请扫码/账密登录卖家账号 → 成功后自动写回
config/1688_cookies.json，并再跑一次无头登录校验。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.publish.session import ROOT, check_login, interactive_login

def main() -> int:
    shot = ROOT / "output" / "_m4" / "login_after_refresh.png"
    print("打开有头浏览器，请完成 1688 登录…")
    r = interactive_login(timeout_sec=300, shot=shot)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    if not r.get("ok"):
        print("\n[失败] 未在时限内完成登录，cookie 未更新。")
        return 1

    print("\n复验登录态（无头）…")
    v = check_login(shot=ROOT / "output" / "_m4" / "login_check.png")
    print(json.dumps(v, ensure_ascii=False, indent=2))
    print("\n登录态:", "[有效]" if v.get("logged_in") else "[仍失效]")
    return 0 if v.get("logged_in") else 2


if __name__ == "__main__":
    raise SystemExit(main())
