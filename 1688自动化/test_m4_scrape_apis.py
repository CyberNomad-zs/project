# -*- coding: utf-8 -*-
"""从方案页抓完整 API 列表（含文档链接），写入 docs/m4_api_inventory.md。

用法:
  .venv-m4\\Scripts\\python.exe test_m4_scrape_apis.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from src.publish.session import COOKIE_PATH, ROOT, browser_session

OUT_JSON = ROOT / "output" / "_m4" / "api_inventory.json"
OUT_MD = ROOT / "docs" / "m4_api_inventory.md"
SOLUTION = (
    "https://open.1688.com/solution/solutionDetail.htm?solutionKey=1671675923686"
)


def main() -> int:
    with browser_session(headless=True, cookie_path=COOKIE_PATH) as page:
        page.goto(SOLUTION, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        # 点 API 及消息列表
        for t in ("API及消息列表", "API"):
            try:
                loc = page.locator(f"text={t}").first
                if loc.count() and loc.is_visible(timeout=1000):
                    loc.click(timeout=3000)
                    page.wait_for_timeout(2000)
                    break
            except Exception:
                pass

        # 滚到底多加载
        for _ in range(8):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(400)

        data = page.evaluate(
            """() => {
              const rows = [];
              // table rows
              document.querySelectorAll('table tr').forEach(tr => {
                const cells = Array.from(tr.querySelectorAll('td,th')).map(c => (c.innerText||'').trim());
                const link = tr.querySelector('a[href*="apidocdetail"]');
                if (cells.length >= 2) {
                  rows.push({
                    cells,
                    doc: link ? link.href : null,
                  });
                }
              });
              // also all apidocdetail links with nearby text
              const links = Array.from(document.querySelectorAll('a[href*="apidocdetail"]')).map(a => {
                const tr = a.closest('tr');
                const cells = tr ? Array.from(tr.querySelectorAll('td')).map(c => (c.innerText||'').trim()) : [];
                return { href: a.href, text: (a.innerText||'').trim(), cells };
              });
              // 开发人员参考 SDK 文案
              let devRef = '';
              try {
                const all = document.body.innerText || '';
                const idx = all.indexOf('前端 JS SDK');
                if (idx >= 0) devRef = all.slice(idx, idx + 2500);
              } catch (e) {}
              return {
                title: document.title,
                url: location.href,
                rows,
                links,
                devRef,
                bodySample: (document.body.innerText || '').slice(0, 12000),
              };
            }"""
        )

        # 解析 API 名
        apis = []
        seen = set()
        for link in data.get("links") or []:
            href = link.get("href") or ""
            m = re.search(r"id=([^&]+)", href)
            api_id = m.group(1) if m else None
            cells = link.get("cells") or []
            # cells 常见: [类别?, 中文名, APIName, 查看链接]
            name = None
            cname = None
            category = None
            if len(cells) >= 3:
                # 尝试找带点的 api name
                for c in cells:
                    if re.search(r"^[a-z0-9]+(\.[a-zA-Z0-9_]+)+$", c):
                        name = c
                    elif c and c not in ("查看链接",) and not re.search(r"^[a-z0-9]+(\.|$)", c):
                        if cname is None and len(c) < 40:
                            cname = c
                if len(cells) >= 1 and len(cells[0]) < 20:
                    category = cells[0] if cells[0] not in (cname, name) else None
            if not name and api_id:
                # com.alibaba.product:alibaba.new.product.add-1
                m2 = re.search(r":([a-zA-Z0-9._]+)-\d+$", api_id)
                if m2:
                    name = m2.group(1)
            key = name or href
            if key in seen:
                continue
            seen.add(key)
            apis.append(
                {
                    "api": name,
                    "cname": cname,
                    "category": category,
                    "doc": href,
                    "api_id": api_id,
                    "cells": cells,
                }
            )

        # 从 body 再补一轮 APIName
        for m in re.finditer(
            r"(alibaba\.[a-zA-Z0-9.]+|product\.[a-zA-Z0-9.]+|bussiness\.[a-zA-Z0-9.]+|relative\.[a-zA-Z0-9.]+|main\.[a-zA-Z0-9.]+|com\.alibaba\.[a-zA-Z0-9.]+)",
            data.get("bodySample") or "",
        ):
            name = m.group(1)
            if name in seen or name.endswith("."):
                continue
            if len(name) < 8:
                continue
            seen.add(name)
            apis.append({"api": name, "cname": None, "category": None, "doc": None, "api_id": None})

        inventory = {
            "source": SOLUTION,
            "scraped_title": data.get("title"),
            "api_count": len(apis),
            "apis": apis,
            "dev_ref_excerpt": data.get("devRef"),
        }
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")

        # Markdown
        lines = [
            "# 1688 新版商品管理方案 · API 清单（自动抓取）",
            "",
            f"> 来源：[{SOLUTION}]({SOLUTION})",
            f"> 抓取时间：本机运行 `test_m4_scrape_apis.py`",
            f"> 方案：新版商品管理解决方案（商家自用版）solutionKey=1671675923686",
            "",
            "## 发布链路关键 API（优先实现）",
            "",
            "| 用途 | APIName | 文档 |",
            "|---|---|---|",
        ]
        priority = [
            ("类目搜索", "alibaba.category.searchByKeyword"),
            ("类目详情", "alibaba.category.get"),
            ("发布 Schema", "alibaba.new.product.getSchema"),
            ("级联子 Schema", "alibaba.new.product.getSubSchema"),
            ("新版发布", "alibaba.new.product.add"),
            ("新版编辑", "alibaba.new.product.edit"),
            ("图片银行上传", "alibaba.photobank.photo.add"),
            ("相册列表", "alibaba.photobank.album.getList"),
            ("视频上传", "alibaba.video.videocenter.upload"),
            ("视频查询", "alibaba.video.videocenter.get"),
            ("视频绑定", "alibaba.video.videocenter.attach"),
            ("运费模板", "alibaba.logistics.myFreightTemplate.list.get"),
            ("发货地址", "alibaba.logistics.mySendGoodsAddress.list.get"),
        ]
        by_name = {a.get("api"): a for a in apis if a.get("api")}
        for use, name in priority:
            a = by_name.get(name) or {}
            doc = a.get("doc") or ""
            doc_md = f"[文档]({doc})" if doc else "—"
            lines.append(f"| {use} | `{name}` | {doc_md} |")

        lines += [
            "",
            "## 全量 API（方案页）",
            "",
            "| APIName | 中文名 | 文档 |",
            "|---|---|---|",
        ]
        for a in sorted(apis, key=lambda x: (x.get("api") or "")):
            name = a.get("api") or "(unknown)"
            cname = a.get("cname") or ""
            doc = a.get("doc") or ""
            doc_md = f"[文档]({doc})" if doc else "—"
            # 过滤噪声
            if name.startswith("com.alibaba.") and not a.get("doc"):
                continue
            lines.append(f"| `{name}` | {cname} | {doc_md} |")

        lines += [
            "",
            "## 前端 JS SDK（方案页「开发人员参考」摘录）",
            "",
            "```",
            (data.get("devRef") or "(未抓到，见 open 方案页#developmentReference)")[:2000],
            "```",
            "",
            "## 备注",
            "",
            "- 发布强制配合前端 JS SDK（`pcAlgorithmSdk`），见 `docs/m4_findings.md`。",
            "- 确切参数以各 API 文档页为准；本清单只作索引。",
            f"- 原始 JSON：`output/_m4/api_inventory.json`",
            "",
        ]
        OUT_MD.parent.mkdir(parents=True, exist_ok=True)
        OUT_MD.write_text("\n".join(lines), encoding="utf-8")
        print(f"apis: {len(apis)}")
        print(f"json: {OUT_JSON}")
        print(f"md:   {OUT_MD}")
        # 打印优先 API 是否命中
        for use, name in priority:
            hit = name in by_name
            print(f"  [{'OK' if hit else 'MISS'}] {use}: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
