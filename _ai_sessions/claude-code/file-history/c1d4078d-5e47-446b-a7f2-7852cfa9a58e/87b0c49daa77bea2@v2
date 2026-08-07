// content_wms.js —— WMS（海外仓）页面内操作，照搬 automation/wms.py。
// 注入到 193.112.93.60:9999 的 frame。承载订单表的 frame 干活，其余返回 null。
window.__HWC_WMS = window.__HWC_WMS || (function () {
  const H = window.__HWC;

  function isOrderFrame() {
    return !!(document.querySelector(".el-table") || H.findByExactText("批量发货"));
  }

  // 读页面顶部「Hi，XXX」显示名（判断当前登录的是金猫/黑猫）。读不到返回 ''。
  function currentAccount() {
    let acc = "";
    for (const e of H.qsa("*")) {
      if (e.children.length || e.offsetParent === null) continue;
      const m = (e.innerText || "").trim().match(/Hi[，,]\s*(.+)$/);
      if (m) acc = m[1].trim();
    }
    return acc;
  }

  // 未发货订单数：优先读 .el-pagination__total「共N条」（固定列使 .el-table__row 翻倍，别直接数）。
  function countRows() {
    const el = document.querySelector(".el-pagination__total");
    if (el) { const m = (el.innerText || "").match(/\d+/); if (m) return +m[0]; }
    const rows = H.qsa(".el-table__row");
    return rows.length ? Math.floor(rows.length / 2) : 0;
  }

  async function closeTips(rounds = 4) {
    const texts = [];
    for (let i = 0; i < rounds; i++) {
      const box = H.qsa(".el-message-box__wrapper .el-message-box").find((b) => H.isVisible(b));
      if (!box) break;
      texts.push((box.innerText || "").trim().slice(0, 120));
      const btn = H.qsa(".el-message-box__wrapper button").find((b) =>
        H.isVisible(b) && ["ok", "OK", "确定", "确认", "关闭", "知道了"].includes(H.norm(b.innerText)));
      if (btn) H.realClick(btn);
      else try { document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); } catch (e) {}
      await H.sleep(1000);
    }
    return texts;
  }

  // 等加载遮罩 .loading-indicator-overlay 消失（改快递方后列表刷新的遮罩会拦截点击）。
  async function waitLoadingGone(L, timeout = 15000) {
    const gone = await H.waitFor(() => !H.qsa(".loading-indicator-overlay").some((el) => H.isVisible(el)),
      { timeout, interval: 300 });
    if (!gone) L.push("[WMS] ⚠️ 等待加载遮罩消失超时，继续尝试");
  }

  async function ensureUnshipped(L) {
    const btn = H.findByExactText("查询");
    if (btn) { H.realClick(btn); await H.sleep(3000); }
    else L.push("[WMS] 未找到『查询』按钮");
  }

  async function selectAll(L) {
    const cb = document.querySelector(".el-table__header-wrapper .el-checkbox, .el-table__header .el-checkbox");
    if (!cb) { L.push("[WMS] 未找到表头全选框"); return false; }
    if ((cb.getAttribute("class") || "").includes("is-disabled")) { L.push("[WMS] 全选框禁用（无数据）"); return false; }
    H.realClick(cb);
    await H.sleep(1000);
    return true;
  }

  function closeDialog() {
    const b = H.qsa(".el-dialog button, .el-dialog .el-dialog__headerbtn").find((x) =>
      H.isVisible(x) && (["取消"].includes(H.norm(x.innerText)) || x.classList.contains("el-dialog__headerbtn")));
    if (b) H.realClick(b);
    else try { document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); } catch (e) {}
  }

  // 批量修改快递方 = courier。DRY 下不点确认。
  async function setCourier(courier, dry, L) {
    const open = H.findByExactText("批量修改快递方");
    if (!open) { L.push("[WMS] 未找到『批量修改快递方』按钮"); return false; }
    H.realClick(open);
    await H.sleep(1500);
    // 可见弹窗内的快递方下拉
    const sel = H.qsa(".el-dialog .el-select").find((s) => H.isVisible(s));
    if (!sel) { L.push("[WMS] 未找到可见的快递方下拉"); closeDialog(); return false; }
    H.realClick(sel);
    await H.sleep(1000);
    const opt = H.qsa(".el-select-dropdown__item").find((o) => H.isVisible(o) && (o.innerText || "").trim() === courier);
    if (!opt) { L.push(`[WMS] 未找到快递方选项 ${courier}`); closeDialog(); return false; }
    H.realClick(opt);
    await H.sleep(500);
    if (dry) { L.push(`[WMS][DRY] 将设置快递方 = ${courier}（跳过确认）`); closeDialog(); return true; }
    const ok = H.qsa(".el-dialog button.el-button--primary, .el-dialog button").find((b) =>
      H.isVisible(b) && (b.classList.contains("el-button--primary") || ["确认", "确定"].includes(H.norm(b.innerText))));
    if (!ok) { L.push("[WMS] 未找到快递方确认按钮"); return false; }
    H.realClick(ok);
    await H.sleep(2000);
    const tips = await closeTips();
    L.push(`[WMS] 已设置快递方 = ${courier}  Tip=${JSON.stringify(tips)}`);
    return true;
  }

  // 需求2：改快递方后设「是否偏远地区」= 否 并查询（只发非偏远，偏远单留存）。
  async function setRemoteFilter(value, L) {
    await closeTips();
    await waitLoadingGone(L);
    const input = document.querySelector("input[placeholder*='偏远']");
    if (!input) { L.push("[WMS] 未找到「是否偏远地区」控件"); return false; }
    H.realClick(input);
    await H.sleep(1000);
    const opt = H.qsa(".el-select-dropdown__item").find((o) => H.isVisible(o) && (o.innerText || "").trim() === value);
    if (!opt) { L.push(`[WMS] 未找到「是否偏远地区」选项「${value}」`); return false; }
    H.realClick(opt);
    await H.sleep(500);
    await waitLoadingGone(L);
    const q = H.findByExactText("查询");
    if (q) { H.realClick(q); await H.sleep(3000); }
    L.push(`[WMS] 已设置 是否偏远地区 = ${value} 并查询（偏远单排除、留存）`);
    return true;
  }

  async function batchShip(dry, L) {
    if (dry) { L.push("[WMS][DRY] 将点击『批量发货』（已跳过）"); return true; }
    const b = H.findByExactText("批量发货");
    if (!b) { L.push("[WMS] 未找到『批量发货』按钮"); return false; }
    H.realClick(b);
    await H.sleep(2000);
    // 可能的二次确认
    const cf = H.qsa(".el-message-box__wrapper button, .el-dialog button").find((x) =>
      H.isVisible(x) && ["确定", "确认", "ok", "OK"].includes(H.norm(x.innerText)));
    if (cf) { H.realClick(cf); await H.sleep(1500); }
    await H.sleep(2000);
    const tips = await closeTips();
    const ok = tips.some((t) => t.includes("成功"));
    L.push(`[WMS] 已执行批量发货  结果Tip=${JSON.stringify(tips)}`);
    return tips.length ? ok : true;
  }

  function readOrderNumbers() {
    const s = new Set();
    H.qsa(".el-table__row").forEach((r) => {
      const m = (r.innerText || "").match(/P[0-9A-Z]{9,15}/g);
      if (m) m.forEach((x) => s.add(x));
    });
    return [...s];
  }

  // ===== 主 op：处理单个店铺 =====
  // 假定 background 已把 WMS 标签页导航到 平台订单页、且当前登录就是本渠道对应店铺。
  async function processShop({ courier, dry }) {
    const L = [];
    if (!courier) { L.push("[WMS] ⚠️ 未解析出快递方，跳过发货"); return { logs: L, error: "无快递方", left_orders: [] }; }
    await ensureUnshipped(L);
    const before = countRows();
    L.push(`[WMS] 未发货订单 ≈ ${before} 条`);
    if (before === 0) return { logs: L, before: 0, left: 0, left_orders: [] };

    L.push(`[WMS] 用快递方 [${courier}] 处理 ${before} 条`);
    // 偏远单（设「偏远=否」后被排除的）本轮不发、直接留存。必须在设偏远前抓全量、设偏远后抓非偏远，
    // 差集=偏远单——否则最后统计仍处于「偏远=否」筛选口径，偏远单读不到 → shipped 虚高、留存漏报。
    let remoteOrders = [];
    if (!(await selectAll(L))) L.push("[WMS] 无法全选，本渠道未发货");
    else if (!(await setCourier(courier, dry, L))) L.push(`[WMS] 改快递方 ${courier} 未成功，本渠道未发货`);
    else {
      const allOrders = readOrderNumbers();   // 改快递方后、加偏远筛选前的全部未发货（当前页）
      if (!(await setRemoteFilter("否", L))) L.push("[WMS] 设偏远=否 未成功，为避免误发偏远单，本渠道未发货");
      else {
        const nonRemote = new Set(readOrderNumbers());
        remoteOrders = allOrders.filter((o) => !nonRemote.has(o));
        if (remoteOrders.length)
          L.push(`[WMS] 偏远单排除、留存 ${remoteOrders.length} 条：${JSON.stringify(remoteOrders)}`);
        if (!(await selectAll(L))) L.push("[WMS] 改快递方后重新全选失败，本渠道未发货");
        else { await batchShip(dry, L); await H.sleep(2000); }
      }
    }

    // 剩余统计：此刻列表若走到过设偏远步骤，仍是「偏远=否」口径 → countRows/readOrderNumbers 只反映
    // 非偏远。故把偏远单单独并回来，才是完整的“仍未发货”。
    await ensureUnshipped(L);
    const leftNonRemote = countRows();
    const leftNonRemoteOrders = leftNonRemote ? readOrderNumbers() : [];
    const left_orders = [...new Set([...remoteOrders, ...leftNonRemoteOrders])];
    const left = remoteOrders.length + leftNonRemote;
    L.push(`[WMS] 处理完成，仍未发货 ≈ ${left} 条（偏远留存 ${remoteOrders.length} + 非偏远未发 ${leftNonRemote}）${dry ? "（DRY 未真正发货）" : ""}`);
    if (left_orders.length && !dry)
      L.push(`[WMS] ⚠️ 留存单（偏远单 + 用 ${courier} 发货后仍未发；不换快递方）：${JSON.stringify(left_orders)}`);
    return { logs: L, before, left, left_orders, remote_orders: remoteOrders, shipped: Math.max(0, before - left) };
  }

  async function dispatch(msg) {
    if (msg.op === "currentAccount") return { display: currentAccount() };  // 任意 frame 都可读
    if (!isOrderFrame()) return null;
    try {
      if (msg.op === "ping") return { ok: true };
      if (msg.op === "processShop") return await processShop(msg);
      return { error: "未知 op: " + msg.op };
    } catch (e) {
      return { error: String((e && e.stack) || e) };
    }
  }

  return { dispatch };
})();
