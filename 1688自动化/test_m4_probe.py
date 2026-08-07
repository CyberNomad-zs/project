# -*- coding: utf-8 -*-
"""M4 发布页 / JS SDK 探针入口。

用法:
  .venv-m4\\Scripts\\python.exe test_m4_probe.py
  .venv-m4\\Scripts\\python.exe test_m4_probe.py --headed
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.publish.probe import run_probe
from src.publish.session import ROOT


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--headed", action="store_true", help="有头模式（调试）")
    args = ap.parse_args()

    report = run_probe(headless=not args.headed)
    # 控制台只打摘要，全量在 probe_report.json
    summary = {
        "login": report.get("login"),
        "error": report.get("error"),
        "hint": report.get("hint"),
        "pages": [
            {
                "url": p.get("url"),
                "final_url": p.get("final_url"),
                "title": p.get("title"),
                "logged_in": p.get("logged_in"),
                "status": p.get("status"),
                "interesting_src": (p.get("inventory") or {}).get("interesting_src"),
                "sdk_inject": bool((p.get("sdk_inject") or {}).get("injected")),
                "error": p.get("error"),
            }
            for p in (report.get("pages") or [])
        ],
        "analysis": report.get("analysis"),
        "report_path": report.get("report_path"),
        "force_inject": {
            "injected": (report.get("force_inject_on_home") or {}).get("injected"),
            "sdk_global": ((report.get("force_inject_on_home") or {}).get("load") or {}).get(
                "hasSdk"
            ),
            "pcAlgorithmSdk": ((report.get("force_inject_on_home") or {}).get("load") or {}).get(
                "pcAlgorithmSdk"
            ),
            "error": (report.get("force_inject_on_home") or {}).get("error")
            or ((report.get("force_inject_on_home") or {}).get("load") or {}).get("error"),
        },
        "network_event_count": report.get("network_event_count"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n完整报告:", report.get("report_path") or (ROOT / "output" / "_m4" / "probe_report.json"))
    if report.get("error") == "not_logged_in":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
