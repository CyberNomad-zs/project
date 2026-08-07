// ============================================================================
// ERP 下拉探针 —— 诊断「筛选模板 / 渠道」弹层为何读到空选项。
// 用法：
//   1) 在真实浏览器打开 ERP 订单页（待处理视图）：
//      https://www.sellfox.com/amzup-web-main/web/orderShip/index.html
//   2) F12 打开控制台，在控制台顶部的【frame 上下文下拉】里
//      选中承载订单表的那个 frame（通常是 orderShip/index.html，不是 top）。
//      —— 选错 frame 会找不到表格，探针会提示。
//   3) 把本文件全部内容粘贴进控制台回车，等它跑完（约 8 秒），
//      把打印出来的整段 [PROBE] 日志复制发回。
// 本探针【只点击、不下单、不发货】，安全。
// ============================================================================
(async () => {
  const P = (...a) => console.log("[PROBE]", ...a);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const norm = (s) => (s || "").replace(/　/g, " ").replace(/\s/g, "");
  const qsa = (sel) => [...document.querySelectorAll(sel)];
  const isVisible = (el) => {
    if (!el) return false;
    const st = getComputedStyle(el);
    if (st.display === "none" || st.visibility === "hidden" || st.opacity === "0") return false;
    if (el.offsetParent === null && st.position !== "fixed") return false;
    return true;
  };
  const realClick = (el) => {
    try { el.scrollIntoView({ block: "center" }); } catch (e) {}
    const r = el.getBoundingClientRect();
    const base = { bubbles: true, cancelable: true, view: window,
      clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, button: 0, buttons: 1 };
    for (const t of ["pointerover", "pointerenter", "pointerdown", "mousedown", "pointerup", "mouseup", "click"]) {
      let ev;
      try { ev = t.startsWith("pointer") ? new PointerEvent(t, { ...base, pointerId: 1, isPrimary: true }) : new MouseEvent(t, base); }
      catch (e) { ev = new MouseEvent(t.replace("pointer", "mouse"), base); }
      el.dispatchEvent(ev);
    }
  };
  const short = (s, n = 60) => { s = (s || "").replace(/\s+/g, " ").trim(); return s.length > n ? s.slice(0, n) + "…" : s; };
  const desc = (el) => {
    if (!el) return "null";
    const cls = (el.getAttribute("class") || "").slice(0, 60);
    return `<${el.tagName.toLowerCase()} class="${cls}"> "${short(el.innerText, 40)}"`;
  };

  // ---- frame 自检 ----
  P("URL =", location.href);
  const hasTable = !!document.querySelector(".vxe-table, .vxe-header--column");
  P("本 frame 是否含 vxe 订单表 =", hasTable);
  if (!hasTable) {
    P("⚠️ 当前 frame 没有订单表！请在控制台顶部 frame 下拉里改选 orderShip/index.html 那个 frame，再重跑本探针。");
    // 不 return，继续探测下拉，或许仍有信息
  }

  // ============ 1) 筛选模板 ============
  P("========== [1] 筛选模板 ==========");
  const tplTriggers = qsa("button, .el-button, span, div, li, a, [class*=btn]")
    .filter((e) => norm(e.innerText) === norm("筛选模板") && isVisible(e));
  P(`文本恰为「筛选模板」的可见元素 = ${tplTriggers.length} 个：`);
  tplTriggers.forEach((e, i) => P(`   #${i} ${desc(e)}  y=${Math.round(e.getBoundingClientRect().top)}`));
  if (tplTriggers.length) {
    // 取 y 最靠上的（与扩展 findByExactText 一致）
    const trig = tplTriggers.slice().sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)[0];
    P("点击 #0（y 最靠上）:", desc(trig));
    const before = new Set(qsa(".el-popper, .el-popover, .el-dropdown-menu, .el-select-dropdown"));
    realClick(trig);
    await sleep(1500);
    const poppers = qsa(".el-popper, .el-popover, .el-dropdown-menu, .el-select-dropdown");
    const newVisible = poppers.filter((p) => isVisible(p));
    P(`点击后 可见弹层(.el-popper/.el-popover/.el-dropdown-menu/.el-select-dropdown) = ${newVisible.length} 个，其中新增 ${poppers.filter((p) => !before.has(p)).length} 个`);
    newVisible.forEach((p, i) => P(`   弹层#${i} ${desc(p)}`));
    // 弹层里有没有「未取消等待发货」
    const hit = qsa("span, div, li, a").filter((e) => isVisible(e) && norm(e.innerText) === norm("未取消等待发货"));
    P(`文本恰为「未取消等待发货」的可见元素 = ${hit.length} 个`);
    hit.forEach((e, i) => P(`   命中#${i} ${desc(e)}`));
    // 弹层里所有短文本候选（帮助看真实模板名/结构）
    if (newVisible.length) {
      const leaves = qsa("span, li, a, div, td, p").filter((e) =>
        isVisible(e) && e.children.length === 0 && norm(e.innerText).length > 0 && norm(e.innerText).length < 20 &&
        newVisible.some((p) => p.contains(e)));
      P("弹层内叶子短文本（去重前 40 个）:", [...new Set(leaves.map((e) => (e.innerText || "").trim()))].slice(0, 40));
    }
    try { document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); } catch (e) {}
    await sleep(500);
  } else {
    P("⚠️ 没有任何可见元素文本恰为「筛选模板」。列出含「筛选/模板」字样的可见元素以便定位真实触发点：");
    qsa("button, .el-button, span, div, li, a, [class*=btn]")
      .filter((e) => isVisible(e) && /筛选|模板/.test(e.innerText || "") && e.children.length <= 2)
      .slice(0, 15).forEach((e, i) => P(`   #${i} ${desc(e)}`));
  }

  // ============ 2) 渠道 ============
  P("========== [2] 渠道 ==========");
  const chanInputs = qsa("input[placeholder*='渠道']");
  P(`input[placeholder*='渠道'] = ${chanInputs.length} 个：`);
  chanInputs.forEach((e, i) => P(`   #${i} placeholder="${e.placeholder}" visible=${isVisible(e)}`));
  const chanTrig = chanInputs.find((e) => isVisible(e)) || chanInputs[0];
  if (chanTrig) {
    P("点击渠道输入框:", `placeholder="${chanTrig.placeholder}"`);
    realClick(chanTrig);
    await sleep(1500);
    const labels = qsa("span.main_label");
    const visLabels = labels.filter((e) => isVisible(e));
    P(`span.main_label 总数 = ${labels.length}，其中可见 = ${visLabels.length}`);
    P("可见 span.main_label 文本:", [...new Set(visLabels.map((e) => (e.innerText || "").trim()).filter(Boolean))].sort());
    if (labels.length && !visLabels.length) {
      P("⚠️ main_label 存在但全不可见 → 弹层可能没真正展开。示例元素:", desc(labels[0]));
    }
    // 弹层容器
    const dds = qsa(".el-popper, .el-select-dropdown, .el-popover, .el-cascader__dropdown").filter((p) => isVisible(p));
    P(`点击后可见下拉容器 = ${dds.length} 个`);
    dds.forEach((p, i) => P(`   容器#${i} ${desc(p)}`));
    try { document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); } catch (e) {}
  } else {
    P("⚠️ 没有 input[placeholder*='渠道']。列出所有可见 input 的 placeholder 以便定位：");
    qsa("input").filter(isVisible).slice(0, 20).forEach((e, i) => P(`   #${i} placeholder="${e.placeholder}"`));
    P("另列出含「渠道」字样的可见元素:");
    qsa("span, div, label, button").filter((e) => isVisible(e) && /渠道/.test(e.innerText || "") && e.children.length <= 2)
      .slice(0, 15).forEach((e, i) => P(`   #${i} ${desc(e)}`));
  }
  P("========== 探针结束，请把以上全部 [PROBE] 行复制发回 ==========");
})();
