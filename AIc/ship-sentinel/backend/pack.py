# -*- coding: utf-8 -*-
"""
打包器：unified.json ->
  1) frontend/data.js         —— window.SENTINEL_DATA=...；供 frontend/index.html 通过 <script src> 加载
                                 （script 标签在 file:// 下可用，fetch 不行，故双击即用）
  2) dist/发货哨兵-离线演示.html —— 把 data.js 内联进 index.html，单文件、断网可演示、可发给评委
"""
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UNIFIED = os.path.join(HERE, "unified.json")
FRONTEND = os.path.join(ROOT, "frontend", "index.html")
DATA_JS = os.path.join(ROOT, "frontend", "data.js")
DIST_DIR = os.path.join(ROOT, "dist")
DIST_HTML = os.path.join(DIST_DIR, "发货哨兵-离线演示.html")


def main():
    with open(UNIFIED, encoding="utf-8") as f:
        data = json.load(f)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    data_js = "window.SENTINEL_DATA=" + payload + ";\n"

    with open(DATA_JS, "w", encoding="utf-8") as f:
        f.write(data_js)

    # 内联到单文件
    with open(FRONTEND, encoding="utf-8") as f:
        html = f.read()
    inline_tag = '<script>\n' + data_js + '</script>'
    html_single = html.replace('<script src="data.js"></script>', inline_tag)
    if inline_tag not in html_single:
        raise RuntimeError("未找到 data.js 注入点，请检查 index.html 中的 <script src=\"data.js\"></script>")

    os.makedirs(DIST_DIR, exist_ok=True)
    with open(DIST_HTML, "w", encoding="utf-8") as f:
        f.write(html_single)

    print("data.js       ->", DATA_JS, "(%.1f KB)" % (len(data_js) / 1024))
    print("单文件离线演示 ->", DIST_HTML, "(%.1f KB)" % (len(html_single) / 1024))
    print("订单数:", len(data["orders"]), " KPI:", json.dumps(data["kpis"], ensure_ascii=False))


if __name__ == "__main__":
    main()
