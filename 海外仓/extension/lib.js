// lib.js —— 注入到 ERP / WMS 页面的共享 DOM 工具。
// 通过 chrome.scripting.executeScript({files:[...]}) 注入，每次调用都会重跑，故用幂等守卫避免重复定义。
window.__HWC = window.__HWC || (function () {
  const H = {};

  H.sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // 去掉全部空白（含全角空格）再比较文本——ERP/WMS 按钮文字常夹空格（如「关 闭」「物流下单」）。
  H.norm = (s) => (s || "").replace(/　/g, " ").replace(/\s/g, "");

  H.qsa = (sel, root) => [...(root || document).querySelectorAll(sel)];

  // 是否真正可见（排除 display:none / 隐藏弹窗）。用于替代 Playwright 的 :visible。
  H.isVisible = (el) => {
    if (!el) return false;
    if (el.offsetParent === null && getComputedStyle(el).position !== "fixed") return false;
    const st = getComputedStyle(el);
    return st.display !== "none" && st.visibility !== "hidden" && st.opacity !== "0";
  };

  // 【核心】完整鼠标事件序列的合成点击。排雷 spike 已证明：只有派发
  // pointerover→pointerdown→mousedown→pointerup→mouseup→click 完整序列，才能驱动
  // vxe-table / Element-UI 的复选框、下拉、按钮（el.click() 只发 click 常被框架忽略=静默失败）。
  H.realClick = (el) => {
    if (!el) return false;
    try { el.scrollIntoView({ block: "center" }); } catch (e) {}
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const base = { bubbles: true, cancelable: true, view: window, clientX: cx, clientY: cy, button: 0, buttons: 1 };
    for (const type of ["pointerover", "pointerenter", "pointerdown", "mousedown", "pointerup", "mouseup", "click"]) {
      let ev;
      try {
        ev = type.startsWith("pointer")
          ? new PointerEvent(type, { ...base, pointerId: 1, isPrimary: true })
          : new MouseEvent(type, base);
      } catch (e) {
        ev = new MouseEvent(type.replace("pointer", "mouse"), base);
      }
      el.dispatchEvent(ev);
    }
    return true;
  };

  // 轮询等待 fn() 返回真值；超时返回 null。（页面上下文可用 Date.now）
  H.waitFor = async (fn, { timeout = 12000, interval = 300 } = {}) => {
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      try { const v = fn(); if (v) return v; } catch (e) {}
      await H.sleep(interval);
    }
    return null;
  };

  // 在候选选择器里找“去空白后文本 == text、可见、可选排除表格行内”的元素，返回 y 最靠上的一个。
  H.findByExactText = (text, { selectors = "button, .el-button, span, div, li, a, [class*=btn]", excludeRowSel = null } = {}) => {
    let best = null, minY = Infinity;
    for (const el of H.qsa(selectors)) {
      if (H.norm(el.innerText) !== H.norm(text)) continue;
      if (excludeRowSel && el.closest(excludeRowSel)) continue;
      if (!H.isVisible(el)) continue;
      const y = el.getBoundingClientRect().top;
      if (y < minY) { minY = y; best = el; }
    }
    return best;
  };

  return H;
})();
