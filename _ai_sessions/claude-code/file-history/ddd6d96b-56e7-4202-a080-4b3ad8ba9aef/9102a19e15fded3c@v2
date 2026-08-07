// ============================================================================
// ERP 渠道下拉专项探针 —— 定位「渠道」自定义 popover 组件的真实下拉容器 / 选项元素。
// 背景：DRY 空跑实测渠道输入框能定位到(<input.el-input__inner ph="渠道">)，祖先链=
//   el-input > select-container > popover_trigger > popover_box（ERP 自封装组件，非 el-select），
//   但点击后 .el-popover/.select-menu/span.main_label 都不出现 → 旧选择器失配(疑 ERP 改版)。
// 本探针不猜新 class，而是【点击各层触发器后 diff 出新出现的可见元素】，把真实结构打出来。
//
// 用法：
//   1) 浏览器打开 ERP 订单页(待处理视图)，最好先手动选好筛选模板(复现生产时序)。
//   2) F12 控制台，在顶部 frame 下拉选中承载订单表的 frame(orderShip/index.html)。
//   3) 整段粘贴进控制台回车，约 15 秒跑完，把全部 [CH] 行复制发回。
// 只点击、不下单、不发货，安全。
// ============================================================================
(async () => {
  const P = (...a) => console.log("[CH]", ...a);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const qsa = (sel, root) => [...(root || document).querySelectorAll(sel)];
  const isVisible = (el) => {
    if (!el) return false;
    const st = getComputedStyle(el);
    if (st.display === "none" || st.visibility === "hidden" || st.opacity === "0") return false;
    if (el.offsetParent === null && st.position !== "fixed") return false;
    return true;
  };
  const cls1 = (el) => (typeof el.className === "string" ? el.className : "").trim().split(/\s+/)[0] || "";
  const short = (s, n = 50) => { s = (s || "").replace(/\s+/g, " ").trim(); return s.length > n ? s.slice(0, n) + "…" : s; };
  const desc = (el) => {
    if (!el) return "null";
    const c = (el.getAttribute("class") || "").slice(0, 70);
    return `<${el.tagName.toLowerCase()} class="${c}"> "${short(el.innerText, 30)}"`;
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
  // 当前全文档「可见元素」集合快照——用于点击前后 diff。
  const visibleSet = () => new Set(qsa("body *").filter(isVisible));
  // 点击后新出现的可见元素，按首个 class 归组打印（找真实下拉容器 / 选项）。
  const dumpNewVisible = (before, label) => {
    const now = qsa("body *").filter(isVisible);
    const fresh = now.filter((e) => !before.has(e));
    P(`  【${label}】点击后新出现可见元素 = ${fresh.length} 个`);
    if (!fresh.length) return fresh;
    // 按 class 归组
    const byCls = {};
    fresh.forEach((e) => { const k = cls1(e) || e.tagName.toLowerCase(); (byCls[k] = byCls[k] || []).push(e); });
    Object.entries(byCls).sort((a, b) => b[1].length - a[1].length).slice(0, 18).forEach(([k, arr]) => {
      P(`     .${k} ×${arr.length}  例:${desc(arr[0])}`);
    });
    // 疑似"选项行"：叶子/短文本、数量>=2 的同类元素
    const leafTexts = [...new Set(fresh.filter((e) => e.children.length === 0 && short(e.innerText, 30))
      .map((e) => (e.innerText || "").trim()).filter(Boolean))].slice(0, 30);
    P(`     新出现叶子短文本(疑选项):`, leafTexts);
    return fresh;
  };
  const esc = () => { try { document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); } catch (e) {} };

  P("URL =", location.href);
  P("本 frame 含订单表 =", !!document.querySelector(".vxe-table, .vxe-header--column"));

  const input = document.querySelector("input[placeholder*='渠道']");
  if (!input) {
    P("⚠️ 没有 input[placeholder*='渠道']。列出可见 input 的 placeholder：");
    qsa("input").filter(isVisible).slice(0, 25).forEach((e, i) => P(`   #${i} ph="${e.placeholder}"`));
    return;
  }
  P("渠道输入框:", desc(input), " readonly=", input.readOnly, " disabled=", input.disabled);

  // 祖先链(带每层 class 全文)，据此确定各层触发候选。
  const chain = [];
  let p = input;
  for (let i = 0; i < 7 && p; i++) { chain.push(p); p = p.parentElement; }
  P("祖先链(内→外):");
  chain.forEach((e, i) => P(`   [${i}] ${desc(e)}`));

  // 依次尝试点击：输入框本身 → select-container → popover_trigger → popover_box。
  // 每次点击前 Esc 关旧弹层 + 快照，点击后 diff 出新可见元素。哪层能"冒出一堆新元素"即真实触发层。
  const targets = [
    { name: "输入框本身", el: input },
    { name: "select-container", el: input.closest(".select-container") },
    { name: "popover_trigger", el: input.closest(".popover_trigger") },
    { name: "popover_box", el: input.closest(".popover_box") },
    { name: "input父层", el: input.parentElement },
  ];
  for (const t of targets) {
    if (!t.el) { P(`—— 跳过「${t.name}」：该层不存在`); continue; }
    esc(); await sleep(400);
    const before = visibleSet();
    P(`—— 点击「${t.name}」: ${desc(t.el)}`);
    realClick(t.el);
    await sleep(1600);
    dumpNewVisible(before, t.name);
    // 顺带报旧选择器命中情况，确认是否真的失配
    P(`     旧选择器现状: el-popover/select-menu 可见=${qsa(".el-popover, .select-menu").filter(isVisible).length}`
      + ` span.main_label 可见=${qsa("span.main_label").filter(isVisible).length}`);
  }
  esc();

  // 兜底：直接把 popover_box 子树结构 dump 出来——有些自定义组件下拉内容常驻 DOM(隐藏)，
  // 选项元素及其 class 可能就藏在里面，不点也能看到。
  const box = input.closest(".popover_box") || input.closest(".select-container");
  if (box) {
    P("—— popover_box/select-container 子树 class 分布(前 25):");
    const clsCount = {};
    qsa("*", box).forEach((e) => { const k = cls1(e); if (k) clsCount[k] = (clsCount[k] || 0) + 1; });
    P("   ", Object.entries(clsCount).sort((a, b) => b[1] - a[1]).slice(0, 25).map(([k, n]) => `${k}:${n}`).join("  "));
  }
  P("========== 渠道探针结束，请把以上全部 [CH] 行复制发回 ==========");
})();
