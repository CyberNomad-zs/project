# -*- coding: utf-8 -*-
"""M4 · 1688 前端 JS SDK（alife-open-sdk / pcAlgorithmSdk）封装。

实测（2026-07-20，见 docs/m4_findings.md）：
- 配置 window.__1688_OPEN_SDK_CONFIG = {appKey, appName}
- 注入 https://o.alicdn.com/fuwu-assets/alife-open-sdk/index.js
- openSdk.load({sdkNameList:['pcAlgorithmSdk']}) →
  getSdkInstance('pcAlgorithmSdk') = {PcAlgorithmInit, PcAlgorithmExecute}
- Init 需 2 参，当前页易报 getModelInfo error；Execute 依赖 Init 成功。

本模块只做浏览器侧加载/调用，不直接发商品。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import Page

ROOT = Path(__file__).resolve().parents[2]
CRED_PATH = ROOT / "config" / "1688_credentials.json"

SDK_CDN = "https://o.alicdn.com/fuwu-assets/alife-open-sdk/index.js"
DEFAULT_APP_KEY = "9901201"
DEFAULT_APP_NAME = "易之来商品自动发布"


def load_app_config(path: Path = CRED_PATH) -> dict:
    """从凭证文件读 appKey；应用名默认用交接文档中的名称。"""
    cfg = {"app_key": DEFAULT_APP_KEY, "app_name": DEFAULT_APP_NAME}
    if Path(path).exists():
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            cfg["app_key"] = str(
                raw.get("app_key") or raw.get("appKey") or cfg["app_key"]
            )
            # 名称以开放平台为准；凭证里若有则覆盖
            if raw.get("app_name") or raw.get("appName"):
                cfg["app_name"] = str(raw.get("app_name") or raw.get("appName"))
        except Exception:
            pass
    return cfg


def inject_open_sdk(
    page: Page,
    app_key: Optional[str] = None,
    app_name: Optional[str] = None,
    spa_type: Optional[str] = None,
    wait_ms: int = 2500,
) -> dict:
    """写入 CONFIG 并注入 alife-open-sdk 脚本。返回状态字典。"""
    app = load_app_config()
    app_key = app_key or app["app_key"]
    app_name = app_name or app["app_name"]

    config: dict[str, Any] = {"appKey": app_key, "appName": app_name}
    if spa_type in ("history", "hash"):
        config["spaType"] = spa_type

    page.evaluate(
        """(cfg) => { window.__1688_OPEN_SDK_CONFIG = cfg; }""",
        config,
    )

    already = page.evaluate("() => typeof window.__1688_OPEN_SDK")
    if already == "undefined":
        page.add_script_tag(url=SDK_CDN)
        page.wait_for_timeout(wait_ms)
    else:
        page.wait_for_timeout(300)

    sdk_type = page.evaluate("() => typeof window.__1688_OPEN_SDK")
    return {
        "config": config,
        "sdk_global_type": sdk_type,
        "ok": sdk_type == "object",
    }


def load_pc_algorithm(page: Page, timeout_ms: int = 10000) -> dict:
    """load pcAlgorithmSdk 并 getSdkInstance。需先 inject_open_sdk。"""
    return page.evaluate(
        """async (timeoutMs) => {
          const out = {};
          const openSdk = window.__1688_OPEN_SDK;
          if (!openSdk) {
            out.error = 'SDK_GLOBAL_MISSING';
            return out;
          }
          out.openSdkKeys = Object.keys(openSdk);
          try {
            const loadRet = await Promise.race([
              openSdk.load({ sdkNameList: ['pcAlgorithmSdk'] }),
              new Promise((_, rej) => setTimeout(() => rej(new Error('load_timeout')), timeoutMs)),
            ]);
            out.loadSuccess = !!(loadRet && loadRet[0] && loadRet[0].success);
            out.load0Keys = loadRet && loadRet[0] ? Object.keys(loadRet[0]) : null;
            const inst = openSdk.getSdkInstance('pcAlgorithmSdk');
            out.instType = typeof inst;
            out.instKeys = inst && typeof inst === 'object' ? Object.keys(inst) : null;
            out.hasInit = !!(inst && typeof inst.PcAlgorithmInit === 'function');
            out.hasExecute = !!(inst && typeof inst.PcAlgorithmExecute === 'function');
            out.ok = !!(out.hasInit && out.hasExecute);
          } catch (e) {
            out.error = String(e);
            out.ok = false;
          }
          return out;
        }""",
        timeout_ms,
    )


def ensure_sdk(page: Page, **inject_kwargs) -> dict:
    """注入 + load，一步到位。"""
    inj = inject_open_sdk(page, **inject_kwargs)
    if not inj.get("ok"):
        return {"ok": False, "stage": "inject", "inject": inj}
    loaded = load_pc_algorithm(page)
    return {
        "ok": bool(loaded.get("ok")),
        "stage": "load" if loaded.get("ok") else "load_failed",
        "inject": inj,
        "load": loaded,
    }


def pc_algorithm_init(page: Page, arg1: Any = None, arg2: Any = None) -> dict:
    """调用 PcAlgorithmInit(arg1, arg2)。

    官方文档写 length=2，但未公开具体字段；当前多页实测返回
    {isInit:false, reason:'getModelInfo error'}，待发布页上下文闭合。
    """
    return page.evaluate(
        """async ({a1, a2}) => {
          const openSdk = window.__1688_OPEN_SDK;
          if (!openSdk) return {error: 'SDK_GLOBAL_MISSING'};
          const inst = openSdk.getSdkInstance('pcAlgorithmSdk');
          if (!inst || typeof inst.PcAlgorithmInit !== 'function') {
            return {error: 'NO_INIT_FN', instType: typeof inst};
          }
          try {
            const args = [];
            if (a1 !== null && a1 !== undefined) args.push(a1);
            if (a2 !== null && a2 !== undefined) args.push(a2);
            // 始终传两个槽位中文档要求的 arity；缺省用 undefined
            while (args.length < 2) args.push(undefined);
            let ret = inst.PcAlgorithmInit(args[0], args[1]);
            if (ret && typeof ret.then === 'function') {
              ret = await Promise.race([
                ret,
                new Promise((_, rej) => setTimeout(() => rej(new Error('init_timeout')), 8000)),
              ]);
            }
            return {ok: true, ret};
          } catch (e) {
            return {ok: false, error: String(e)};
          }
        }""",
        {"a1": arg1, "a2": arg2},
    )


def pc_algorithm_execute(page: Page, payload: Any) -> dict:
    """调用 PcAlgorithmExecute(payload)。Init 未成功时通常返回 reInit Error。"""
    return page.evaluate(
        """async (payload) => {
          const openSdk = window.__1688_OPEN_SDK;
          if (!openSdk) return {error: 'SDK_GLOBAL_MISSING'};
          const inst = openSdk.getSdkInstance('pcAlgorithmSdk');
          if (!inst || typeof inst.PcAlgorithmExecute !== 'function') {
            return {error: 'NO_EXEC_FN'};
          }
          try {
            let ret = inst.PcAlgorithmExecute(payload);
            if (ret && typeof ret.then === 'function') {
              ret = await Promise.race([
                ret,
                new Promise((_, rej) => setTimeout(() => rej(new Error('exec_timeout')), 10000)),
              ]);
            }
            return {ok: true, ret};
          } catch (e) {
            return {ok: false, error: String(e)};
          }
        }""",
        payload,
    )
