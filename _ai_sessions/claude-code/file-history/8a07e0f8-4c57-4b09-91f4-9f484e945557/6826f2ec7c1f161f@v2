// rules.js —— 渠道 -> 店铺/快递方 映射（照搬 automation/rules.py 的业务规则）。
// 由 background.js 通过 importScripts('rules.js') 加载，挂到 self.HWC_RULES。
self.HWC_RULES = (function () {
  // 渠道处理顺序（= 优先级；按此逐渠道闭环 ERP下单 -> WMS发货）。
  const CHANNEL_ORDER = [
    "昇新海外仓-BLACKCAT-RM",
    "昇新海外仓-BLACKCAT-DPD",
    "昇新海外仓-BLACKCAT-EH",
    "昇新海外仓-昇新海外仓-RM",
    "昇新海外仓-昇新海外仓-DPD",
  ];

  const ALL_COURIERS = ["DPD", "RM", "EH", "FEDEX"];

  // 店铺信息：login=WMS登录名；display=页面顶部「Hi，XXX」显示名（金猫≠登录名！实测：
  // 金猫 display=金猫商贸、黑猫 display=JMCAT）。用 display 判断当前 WMS 登录的是哪个店铺。
  const SHOPS = {
    JMCAT: { login: "JMCAT", shop: "黑猫", display: "JMCAT" },
    JMSM:  { login: "JMSM",  shop: "金猫", display: "金猫商贸" },
  };

  // 需求1：物流下单选渠道前先选此模板，排除 已取消/退款/换货/禁处理 的单。
  const FILTER_TEMPLATE = "未取消等待发货";

  // 渠道名含 BLACKCAT => 黑猫 JMCAT；否则 => 金猫 JMSM。
  function channelAccountLogin(ch) {
    return /BLACKCAT/i.test(ch || "") ? "JMCAT" : "JMSM";
  }

  // 渠道末段(-RM/-DPD/-EH) = WMS 要改成的那一个快递方（一一对应，用户规则 2026-07-09）。
  function channelCourier(ch) {
    if (!ch) return "";
    const last = (ch.trim().split("-").pop() || "").trim().toUpperCase();
    return ALL_COURIERS.includes(last) ? last : "";
  }

  // 页面显示名 -> 店铺 login（display 与期望互相包含即视为同一店铺）。读不到返回 null。
  function shopByDisplay(display) {
    const d = (display || "").trim();
    if (!d) return null;
    for (const k of Object.keys(SHOPS)) {
      const exp = SHOPS[k].display;
      if (exp && (d.includes(exp) || exp.includes(d))) return k;
    }
    return null;
  }

  return { CHANNEL_ORDER, ALL_COURIERS, SHOPS, FILTER_TEMPLATE,
           channelAccountLogin, channelCourier, shopByDisplay };
})();
