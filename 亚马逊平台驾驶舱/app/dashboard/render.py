"""将聚合 JSON 渲染为静态 HTML 仪表盘（Chart.js CDN）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.rules.engine import anomaly_type_cn


def _esc(s: Any) -> str:
    t = str(s if s is not None else "")
    return (
        t.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _money(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)


def _pct(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(v)


def _kpi_card(label: str, value: str, tone: str = "") -> str:
    cls = f"kpi {tone}".strip()
    return f'<div class="{cls}"><div class="kpi-v">{_esc(value)}</div><div class="kpi-l">{_esc(label)}</div></div>'


def _task_rows(tasks: list[dict[str, Any]], show_shop: bool = True) -> str:
    if not tasks:
        return '<tr><td colspan="8" class="empty">暂无</td></tr>'
    rows = []
    for t in tasks:
        lv = t.get("level") or ""
        badge = f'<span class="badge {lv}">{_esc(lv)}</span>'
        shop_cell = f"<td>{_esc(t.get('shop_name'))}</td>" if show_shop else ""
        rows.append(
            "<tr>"
            f"{shop_cell}"
            f"<td class='mono'>{_esc(t.get('asin'))}</td>"
            f"<td>{_esc(t.get('title_cn'))}</td>"
            f"<td>{_esc(anomaly_type_cn(t.get('anomaly_type')))}</td>"
            f"<td>{badge}</td>"
            f"<td class='num'>{_esc(t.get('value_summary') or t.get('current_value'))}</td>"
            f"<td>{_esc(t.get('owner'))}</td>"
            f"<td class='mono'>{_esc((t.get('due_at') or '')[:10])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


CSS = """
:root {
  --bg: #0f1419;
  --surface: #1a222c;
  --surface2: #243040;
  --ink: #e8eef4;
  --muted: #8b9aab;
  --line: #2c3a4a;
  --red: #e85d4c;
  --orange: #e8a23c;
  --green: #3dba7a;
  --blue: #4c9aed;
  --gap: 16px;
  --radius: 10px;
  font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); }
a { color: var(--blue); text-decoration: none; }
a:hover { text-decoration: underline; }
.wrap { max-width: 1280px; margin: 0 auto; padding: 20px 20px 48px; }
header.app {
  display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between;
  gap: 12px; margin-bottom: 20px; border-bottom: 1px solid var(--line); padding-bottom: 16px;
}
header.app h1 { margin: 0; font-size: 1.45rem; font-weight: 650; letter-spacing: .02em; }
header.app .meta { color: var(--muted); font-size: .9rem; }
.nav { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 18px; }
.nav a {
  background: var(--surface); border: 1px solid var(--line); color: var(--ink);
  padding: 6px 12px; border-radius: 999px; font-size: .85rem;
}
.nav a.active { border-color: var(--blue); color: var(--blue); }
.nav a:hover { background: var(--surface2); text-decoration: none; }
.kpis {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 10px; margin-bottom: var(--gap);
}
.kpi {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 12px 14px; min-height: 72px;
}
.kpi-v { font-size: 1.45rem; font-weight: 700; line-height: 1.2; }
.kpi-l { color: var(--muted); font-size: .78rem; margin-top: 4px; }
.kpi.red .kpi-v { color: var(--red); }
.kpi.orange .kpi-v { color: var(--orange); }
.kpi.green .kpi-v { color: var(--green); }
.kpi.blue .kpi-v { color: var(--blue); }
.grid2 {
  display: grid; grid-template-columns: 1fr 1fr; gap: var(--gap); margin-bottom: var(--gap);
}
@media (max-width: 900px) { .grid2 { grid-template-columns: 1fr; } }
.card {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 14px 16px; margin-bottom: var(--gap);
}
.card h2 {
  margin: 0 0 12px; font-size: .95rem; font-weight: 600; color: var(--muted);
  text-transform: none; letter-spacing: .04em;
}
.chart-box { position: relative; height: 260px; }
table { width: 100%; border-collapse: collapse; font-size: .82rem; }
th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; font-size: .75rem; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
td.mono { font-family: ui-monospace, Consolas, monospace; font-size: .78rem; }
tr:hover td { background: rgba(255,255,255,.02); }
.badge {
  display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: .72rem; font-weight: 600;
}
.badge.red { background: rgba(232,93,76,.2); color: var(--red); }
.badge.orange { background: rgba(232,162,60,.2); color: var(--orange); }
.badge.yellow { background: rgba(200,180,80,.2); color: #d4c35a; }
.empty { color: var(--muted); text-align: center; padding: 16px !important; }
.footer { color: var(--muted); font-size: .75rem; margin-top: 24px; }
.scroll { max-height: 360px; overflow: auto; }
"""


def _shell(title: str, nav_html: str, body: str, chart_js: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_esc(title)}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
{body}
<p class="footer">ASIN 健康度驾驶舱 · 本地静态页 · 数据来自 SQLite · 图表 Chart.js</p>
</div>
<script>
{chart_js}
</script>
</body>
</html>
"""


def render_group_html(data: dict[str, Any], shops: list[str]) -> str:
    kpi = data.get("kpi") or {}
    day = data.get("biz_date") or "—"
    nav = ['<a class="active" href="index.html">集团总览</a>']
    for s in shops:
        nav.append(f'<a href="shop_{_slug(s)}.html">{_esc(s)}</a>')

    kpis = "".join(
        [
            _kpi_card("红色任务", str(kpi.get("red", 0)), "red"),
            _kpi_card("橙色任务", str(kpi.get("orange", 0)), "orange"),
            _kpi_card("逾期", str(kpi.get("overdue", 0)), "red"),
            _kpi_card("待老板决策", str(kpi.get("boss", 0)), "orange"),
            _kpi_card("销售额", _money(kpi.get("sales")), "blue"),
            _kpi_card("广告花费", _money(kpi.get("ad_cost"))),
            _kpi_card("店级 ACOS", _pct(kpi.get("acos"))),
            _kpi_card("监控 ASIN", str(kpi.get("asins", 0))),
        ]
    )

    shop_task_rows = []
    for r in data.get("shop_tasks") or []:
        shop_task_rows.append(
            f"<tr><td>{_esc(r['shop'])}</td>"
            f"<td class='num'>{r['red']}</td><td class='num'>{r['orange']}</td>"
            f"<td class='num'>{r['overdue']}</td><td class='num'>{r['boss']}</td></tr>"
        )
    if not shop_task_rows:
        shop_task_rows = ['<tr><td colspan="5" class="empty">暂无</td></tr>']

    red_head = "<th>店铺</th><th>ASIN</th><th>品名</th><th>类型</th><th>等级</th><th>指标摘要</th><th>负责人</th><th>截止</th>"

    body = f"""
<header class="app">
  <div>
    <h1>集团总览 · ASIN 健康度</h1>
    <div class="meta">业务日 { _esc(day) } · 生成 { _esc(data.get('generated_at')) }</div>
  </div>
</header>
<nav class="nav">{''.join(nav)}</nav>
<section class="kpis">{kpis}</section>
<div class="grid2">
  <div class="card"><h2>近 7 日销售额</h2><div class="chart-box"><canvas id="cSales"></canvas></div></div>
  <div class="card"><h2>近 7 日红/橙任务（按任务业务日）</h2><div class="chart-box"><canvas id="cTasks"></canvas></div></div>
</div>
<div class="grid2">
  <div class="card"><h2>各店销售额（业务日）</h2><div class="chart-box"><canvas id="cShopSales"></canvas></div></div>
  <div class="card"><h2>各店红色任务</h2><div class="chart-box"><canvas id="cShopRed"></canvas></div></div>
</div>
<div class="grid2">
  <div class="card">
    <h2>跨店风险矩阵</h2>
    <div class="scroll"><table>
      <thead><tr><th>店铺</th><th class="num">红</th><th class="num">橙</th><th class="num">逾期</th><th class="num">老板</th></tr></thead>
      <tbody>{''.join(shop_task_rows)}</tbody>
    </table></div>
  </div>
  <div class="card"><h2>TOP 异常类型</h2><div class="chart-box"><canvas id="cTypes"></canvas></div></div>
</div>
<div class="card">
  <h2>红色任务（未关闭 · Top 25）</h2>
  <div class="scroll"><table>
    <thead><tr>{red_head}</tr></thead>
    <tbody>{_task_rows(data.get('red_tasks') or [], True)}</tbody>
  </table></div>
</div>
<div class="card">
  <h2>待老板决策</h2>
  <div class="scroll"><table>
    <thead><tr>{red_head}</tr></thead>
    <tbody>{_task_rows(data.get('boss_tasks') or [], True)}</tbody>
  </table></div>
</div>
"""
    payload = json.dumps(
        {
            "sales_trend": data.get("sales_trend") or [],
            "task_trend": data.get("task_trend") or [],
            "shop_sales": data.get("shop_sales") or [],
            "shop_tasks": data.get("shop_tasks") or [],
            "top_anomaly_types": data.get("top_anomaly_types") or [],
        },
        ensure_ascii=False,
    )
    chart_js = f"""
const D = {payload};
const grid = {{ color: 'rgba(255,255,255,0.06)' }};
const tick = {{ color: '#8b9aab', maxTicksLimit: 8 }};
Chart.defaults.color = '#8b9aab';
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';

new Chart(document.getElementById('cSales'), {{
  type: 'line',
  data: {{
    labels: D.sales_trend.map(x => x.date.slice(5)),
    datasets: [{{
      label: '销售额', data: D.sales_trend.map(x => x.sales),
      borderColor: '#4c9aed', backgroundColor: 'rgba(76,154,237,0.12)',
      tension: 0.25, fill: true, pointRadius: 3, borderWidth: 2
    }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ ticks: tick, grid }}, y: {{ ticks: tick, grid }} }}
  }}
}});

new Chart(document.getElementById('cTasks'), {{
  type: 'line',
  data: {{
    labels: D.task_trend.map(x => x.date.slice(5)),
    datasets: [
      {{ label: '红', data: D.task_trend.map(x => x.red), borderColor: '#e85d4c', tension: 0.25, pointRadius: 3, borderWidth: 2 }},
      {{ label: '橙', data: D.task_trend.map(x => x.orange), borderColor: '#e8a23c', tension: 0.25, pointRadius: 3, borderWidth: 2 }}
    ]
  }},
  options: {{ responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ position: 'bottom' }} }},
    scales: {{ x: {{ ticks: tick, grid }}, y: {{ ticks: tick, grid, beginAtZero: true }} }}
  }}
}});

new Chart(document.getElementById('cShopSales'), {{
  type: 'bar',
  data: {{
    labels: D.shop_sales.map(x => x.shop),
    datasets: [{{
      label: '销售额', data: D.shop_sales.map(x => x.sales),
      backgroundColor: '#4c9aed', borderRadius: 4
    }}]
  }},
  options: {{ indexAxis: 'y', responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ ticks: tick, grid }}, y: {{ ticks: tick, grid }} }}
  }}
}});

new Chart(document.getElementById('cShopRed'), {{
  type: 'bar',
  data: {{
    labels: D.shop_tasks.map(x => x.shop),
    datasets: [{{
      label: '红色任务', data: D.shop_tasks.map(x => x.red),
      backgroundColor: '#e85d4c', borderRadius: 4
    }}]
  }},
  options: {{ indexAxis: 'y', responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ ticks: tick, grid, beginAtZero: true }}, y: {{ ticks: tick, grid }} }}
  }}
}});

new Chart(document.getElementById('cTypes'), {{
  type: 'bar',
  data: {{
    labels: D.top_anomaly_types.map(x => x.type),
    datasets: [{{
      label: '数量', data: D.top_anomaly_types.map(x => x.count),
      backgroundColor: '#e8a23c', borderRadius: 4
    }}]
  }},
  options: {{ indexAxis: 'y', responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ ticks: tick, grid, beginAtZero: true }}, y: {{ ticks: tick, grid }} }}
  }}
}});
"""
    return _shell(f"集团总览 {day}", "".join(nav), body, chart_js)


def _slug(shop: str) -> str:
    return shop.replace("/", "_").replace("\\", "_").replace(" ", "_")


def render_shop_html(data: dict[str, Any], shops: list[str]) -> str:
    shop = data.get("shop") or "—"
    day = data.get("biz_date") or "—"
    kpi = data.get("kpi") or {}
    nav = ['<a href="index.html">集团总览</a>']
    for s in shops:
        cls = ' class="active"' if s == shop else ""
        nav.append(f'<a{cls} href="shop_{_slug(s)}.html">{_esc(s)}</a>')

    kpis = "".join(
        [
            _kpi_card("红色", str(kpi.get("red", 0)), "red"),
            _kpi_card("橙色", str(kpi.get("orange", 0)), "orange"),
            _kpi_card("逾期", str(kpi.get("overdue", 0)), "red"),
            _kpi_card("销售额", _money(kpi.get("sales")), "blue"),
            _kpi_card("订单量", _money(kpi.get("orders"))),
            _kpi_card("广告花费", _money(kpi.get("ad_cost"))),
            _kpi_card("店 ACOS", _pct(kpi.get("acos")), "orange"),
            _kpi_card("ASIN 数", str(kpi.get("asins", 0))),
        ]
    )

    inv_rows = []
    for r in data.get("inventory_risk") or []:
        inv_rows.append(
            f"<tr><td class='mono'>{_esc(r.get('asin'))}</td><td>{_esc(r.get('title'))}</td>"
            f"<td class='num'>{_esc(r.get('available_days'))}</td>"
            f"<td class='num'>{_esc(r.get('available'))}</td>"
            f"<td class='num'>{_esc(r.get('in_transit'))}</td>"
            f"<td class='num'>{_money(r.get('sales'))}</td></tr>"
        )
    if not inv_rows:
        inv_rows = ['<tr><td colspan="6" class="empty">暂无低库存</td></tr>']

    acos_rows = []
    for r in data.get("high_acos") or []:
        acos_rows.append(
            f"<tr><td class='mono'>{_esc(r.get('asin'))}</td><td>{_esc(r.get('title'))}</td>"
            f"<td class='num'>{_pct(r.get('acos'))}</td>"
            f"<td class='num'>{_money(r.get('ad_cost'))}</td>"
            f"<td class='num'>{_money(r.get('ad_sales'))}</td></tr>"
        )
    if not acos_rows:
        acos_rows = ['<tr><td colspan="5" class="empty">暂无超红线</td></tr>']

    todo_head = "<th>ASIN</th><th>品名</th><th>类型</th><th>等级</th><th>指标摘要</th><th>负责人</th><th>截止</th>"

    body = f"""
<header class="app">
  <div>
    <h1>店盘 · {_esc(shop)}</h1>
    <div class="meta">业务日 {_esc(day)} · 变体 { _esc(', '.join(data.get('shop_variants') or [])) }</div>
  </div>
</header>
<nav class="nav">{''.join(nav)}</nav>
<section class="kpis">{kpis}</section>
<div class="grid2">
  <div class="card"><h2>近 7 日销售额</h2><div class="chart-box"><canvas id="cSales"></canvas></div></div>
  <div class="card"><h2>近 7 日广告花费</h2><div class="chart-box"><canvas id="cAd"></canvas></div></div>
</div>
<div class="card">
  <h2>今日必办 · 红/橙任务</h2>
  <div class="scroll"><table>
    <thead><tr>{todo_head}</tr></thead>
    <tbody>{_task_rows(data.get('todo_tasks') or [], False)}</tbody>
  </table></div>
</div>
<div class="grid2">
  <div class="card"><h2>Top ASIN 销售额</h2><div class="chart-box"><canvas id="cTop"></canvas></div></div>
  <div class="card"><h2>异常类型分布</h2><div class="chart-box"><canvas id="cTypes"></canvas></div></div>
</div>
<div class="grid2">
  <div class="card">
    <h2>库存预警（可售天数 &lt; 30）</h2>
    <div class="scroll"><table>
      <thead><tr><th>ASIN</th><th>品名</th><th class="num">可售天</th><th class="num">可售</th><th class="num">在途</th><th class="num">销售额</th></tr></thead>
      <tbody>{''.join(inv_rows)}</tbody>
    </table></div>
  </div>
  <div class="card">
    <h2>高 ACOS（&gt; 30% 且有花费）</h2>
    <div class="scroll"><table>
      <thead><tr><th>ASIN</th><th>品名</th><th class="num">ACOS</th><th class="num">花费</th><th class="num">广告销售</th></tr></thead>
      <tbody>{''.join(acos_rows)}</tbody>
    </table></div>
  </div>
</div>
"""
    # ACOS display: Sellfox may store 0-1 or 0-100
    payload = json.dumps(
        {
            "sales_trend": data.get("sales_trend") or [],
            "top_asins": data.get("top_asins") or [],
            "anomaly_types": data.get("anomaly_types") or [],
        },
        ensure_ascii=False,
    )
    chart_js = f"""
const D = {payload};
const grid = {{ color: 'rgba(255,255,255,0.06)' }};
const tick = {{ color: '#8b9aab', maxTicksLimit: 8 }};
Chart.defaults.color = '#8b9aab';

new Chart(document.getElementById('cSales'), {{
  type: 'line',
  data: {{
    labels: D.sales_trend.map(x => x.date.slice(5)),
    datasets: [{{
      label: '销售额', data: D.sales_trend.map(x => x.sales),
      borderColor: '#4c9aed', backgroundColor: 'rgba(76,154,237,0.12)',
      tension: 0.25, fill: true, pointRadius: 3, borderWidth: 2
    }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ ticks: tick, grid }}, y: {{ ticks: tick, grid }} }}
  }}
}});

new Chart(document.getElementById('cAd'), {{
  type: 'line',
  data: {{
    labels: D.sales_trend.map(x => x.date.slice(5)),
    datasets: [{{
      label: '广告花费', data: D.sales_trend.map(x => x.ad_cost),
      borderColor: '#e8a23c', backgroundColor: 'rgba(232,162,60,0.12)',
      tension: 0.25, fill: true, pointRadius: 3, borderWidth: 2
    }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ ticks: tick, grid }}, y: {{ ticks: tick, grid }} }}
  }}
}});

new Chart(document.getElementById('cTop'), {{
  type: 'bar',
  data: {{
    labels: D.top_asins.map(x => (x.title || x.asin || '').slice(0, 18)),
    datasets: [{{
      label: '销售额', data: D.top_asins.map(x => x.sales || 0),
      backgroundColor: '#4c9aed', borderRadius: 4
    }}]
  }},
  options: {{ indexAxis: 'y', responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ ticks: tick, grid }}, y: {{ ticks: tick, grid }} }}
  }}
}});

new Chart(document.getElementById('cTypes'), {{
  type: 'doughnut',
  data: {{
    labels: D.anomaly_types.map(x => x.type),
    datasets: [{{
      data: D.anomaly_types.map(x => x.count),
      backgroundColor: ['#e85d4c','#e8a23c','#4c9aed','#3dba7a','#9b7bff','#5ec8c8','#c4a35a','#888']
    }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ position: 'right', labels: {{ boxWidth: 12 }} }} }}
  }}
}});
"""
    return _shell(f"店盘 {shop} {day}", "".join(nav), body, chart_js)


def write_dashboard_site(
    out_dir: Path,
    group: dict[str, Any],
    shops_payloads: list[dict[str, Any]],
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    shops = [p.get("shop") for p in shops_payloads if p.get("shop")]
    written: list[Path] = []

    # JSON dumps
    (out_dir / "group.json").write_text(
        json.dumps(group, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    written.append(out_dir / "group.json")

    index = out_dir / "index.html"
    index.write_text(render_group_html(group, shops), encoding="utf-8")
    written.append(index)

    for p in shops_payloads:
        shop = p.get("shop") or "unknown"
        path = out_dir / f"shop_{_slug(shop)}.html"
        path.write_text(render_shop_html(p, shops), encoding="utf-8")
        written.append(path)
        jp = out_dir / f"shop_{_slug(shop)}.json"
        jp.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(jp)

    return written
