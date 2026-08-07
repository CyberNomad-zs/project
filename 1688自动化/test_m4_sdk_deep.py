# -*- coding: utf-8 -*-
"""深挖 pcAlgorithmSdk：函数签名 / toString / 试探性调用错误信息。

用法:
  .venv-m4\\Scripts\\python.exe test_m4_sdk_deep.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from src.publish.probe import APP_KEY, APP_NAME, SDK_CDN
from src.publish.session import COOKIE_PATH, ROOT, browser_session

OUT = ROOT / "output" / "_m4"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    with browser_session(headless=True, cookie_path=COOKIE_PATH) as page:
        # 卖家工作台（若 cookie 仍带卖家态更好；否则买家页也能注入 SDK）
        page.goto(
            "https://work.1688.com/?_path_=sellerPro/sellberBaseNew_Index/seller2018IndexPage",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_timeout(2000)
        # 尝试点「切为卖家」
        for sel in ("text=切为卖家", "text=切换为卖家"):
            try:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible(timeout=800):
                    loc.click(timeout=3000)
                    page.wait_for_timeout(2500)
                    break
            except Exception:
                pass

        page.evaluate(
            """({appKey, appName}) => {
              window.__1688_OPEN_SDK_CONFIG = { appKey, appName };
            }""",
            {"appKey": APP_KEY, "appName": APP_NAME},
        )
        page.add_script_tag(url=SDK_CDN)
        page.wait_for_timeout(2500)

        result = page.evaluate(
            """async () => {
              const out = {};
              const sdk = window.__1688_OPEN_SDK;
              out.sdkKeys = sdk ? Object.keys(sdk) : null;
              if (!sdk) { out.error = 'no_sdk'; return out; }

              let loadRet;
              try {
                loadRet = await sdk.load({ sdkNameList: ['pcAlgorithmSdk'] });
                out.loadRet = {
                  type: typeof loadRet,
                  isArray: Array.isArray(loadRet),
                  json: JSON.parse(JSON.stringify(loadRet, (k,v) => {
                    if (typeof v === 'function') return `function:${v.name||'anonymous'}`;
                    if (typeof v === 'object' && v && v.constructor && v.constructor.name !== 'Object' && v.constructor.name !== 'Array') {
                      try { return {__class: v.constructor.name, keys: Object.keys(v)}; } catch(e) { return String(v); }
                    }
                    return v;
                  })),
                };
              } catch (e) {
                out.loadError = String(e);
              }

              const inst = sdk.getSdkInstance('pcAlgorithmSdk');
              out.instType = typeof inst;
              if (!inst) { out.noInst = true; return out; }

              out.instKeys = Object.keys(inst);
              out.methods = {};
              for (const name of Object.keys(inst)) {
                const fn = inst[name];
                const entry = { type: typeof fn };
                if (typeof fn === 'function') {
                  entry.length = fn.length;
                  entry.name = fn.name;
                  try { entry.toString = Function.prototype.toString.call(fn).slice(0, 1500); } catch (e) {
                    entry.toStringError = String(e);
                  }
                }
                out.methods[name] = entry;
              }

              // 试探性调用：空参 / 空对象，收集报错（往往带参数提示）
              out.probes = {};
              const cases = [
                {name: 'Init_noarg', fn: 'PcAlgorithmInit', args: []},
                {name: 'Init_emptyobj', fn: 'PcAlgorithmInit', args: [{}]},
                {name: 'Init_appKey', fn: 'PcAlgorithmInit', args: [{appKey: '9901201'}]},
                {name: 'Init_config', fn: 'PcAlgorithmInit', args: [{appKey:'9901201', appName:'易之来商品自动发布'}]},
                {name: 'Exec_noarg', fn: 'PcAlgorithmExecute', args: []},
                {name: 'Exec_emptyobj', fn: 'PcAlgorithmExecute', args: [{}]},
                {name: 'Exec_api', fn: 'PcAlgorithmExecute', args: [{api:'alibaba.new.product.add'}]},
                {name: 'Exec_str', fn: 'PcAlgorithmExecute', args: ['alibaba.new.product.add']},
              ];
              for (const c of cases) {
                try {
                  const ret = inst[c.fn](...c.args);
                  let resolved = ret;
                  if (ret && typeof ret.then === 'function') {
                    resolved = await Promise.race([
                      ret.then(v => v).catch(e => ({__reject: String(e)})),
                      new Promise(r => setTimeout(() => r({__timeout: true}), 4000)),
                    ]);
                  }
                  out.probes[c.name] = {
                    ok: true,
                    retType: typeof resolved,
                    ret: (() => {
                      try { return JSON.parse(JSON.stringify(resolved)); }
                      catch (e) {
                        if (resolved && typeof resolved === 'object') {
                          return {keys: Object.keys(resolved), str: String(resolved).slice(0,200)};
                        }
                        return String(resolved).slice(0,300);
                      }
                    })(),
                  };
                } catch (e) {
                  out.probes[c.name] = { ok: false, error: String(e), stack: (e && e.stack || '').slice(0, 500) };
                }
              }

              // 看 load 的 result 内部
              try {
                const r0 = loadRet && loadRet[0];
                if (r0 && r0.result) {
                  out.loadResultKeys = Object.keys(r0.result);
                  out.loadResultTypes = {};
                  for (const k of Object.keys(r0.result)) {
                    out.loadResultTypes[k] = typeof r0.result[k];
                  }
                }
              } catch (e) { out.loadResultError = String(e); }

              return out;
            }"""
        )

        path = OUT / "sdk_deep_report.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:8000])
        print("\nreport:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
