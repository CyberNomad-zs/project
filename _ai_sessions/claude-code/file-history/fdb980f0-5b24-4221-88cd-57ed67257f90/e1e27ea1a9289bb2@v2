# -*- coding: utf-8 -*-
"""
快递方（承运商）选择规则。
按 店铺/账号 使用不同的优先列表，从上往下依次尝试；某单当前渠道失败则换下一个，直到成功。
顺序无严格要求，可按需调整。
"""

# 店铺/账号 -> 快递方优先顺序
# 注意：金猫 = 账号 JMSM；黑猫 = 账号 JMCAT
COURIER_RULES = {
    "金猫": ["RM", "DPD"],
    "JMSM": ["RM", "DPD"],            # 金猫账号
    "黑猫": ["RM", "DPD", "EH"],
    "JMCAT": ["RM", "DPD", "EH"],     # 黑猫账号
    # 新增店铺在此追加，例如：
    # "某店铺": ["DPD", "RM"],
}

# 找不到店铺匹配时使用的兜底优先列表
DEFAULT_COURIER_ORDER = ["RM", "DPD"]

# WMS 快递方下拉里可选的全部渠道（用于校验）
ALL_COURIERS = ["DPD", "RM", "EH", "FEDEX"]


# ---- 渠道（ERP「全部渠道」下拉项）-> WMS 账号 + 快递方 ----
# 渠道名含 BLACKCAT => 黑猫 JMCAT；含 昇新海外仓-昇新海外仓（非 BLACKCAT）=> 金猫 JMSM。
# 已知渠道示例：昇新海外仓-BLACKCAT-RM/-DPD/-EH（黑猫）、昇新海外仓-昇新海外仓-RM/-DPD（金猫）。
# ⚠️ 规则（用户 2026-07-09）：渠道末段(-RM/-DPD/-EH) = WMS 批量修改快递方要选的那一个，一一对应。
#    ERP 用哪个渠道下单，WMS 这批单就改成该末段快递方发一次；失败即留存，不换别的快递方（见 channel_courier）。

# 渠道处理顺序（= 优先级；按此逐渠道闭环 ERP下单->WMS发货）。可按实际渠道名调整/扩充。
CHANNEL_ORDER = [
    "昇新海外仓-BLACKCAT-RM",
    "昇新海外仓-BLACKCAT-DPD",
    "昇新海外仓-BLACKCAT-EH",
    "昇新海外仓-昇新海外仓-RM",
    "昇新海外仓-昇新海外仓-DPD",
]


def channel_account_login(channel_name: str) -> str:
    """渠道名 -> WMS 账号登录名（JMCAT=黑猫 / JMSM=金猫）。"""
    return "JMCAT" if "BLACKCAT" in (channel_name or "").upper() else "JMSM"


def channel_courier(channel_name: str) -> str:
    """渠道名末段 -> WMS 快递方（RM/DPD/EH/FEDEX），一一对应（用户规则 2026-07-09）。
    取最后一个 '-' 分段并校验。例：
      '昇新海外仓-昇新海外仓-DPD' -> 'DPD'；'昇新海外仓-BLACKCAT-RM' -> 'RM'。
    解析不出合法快递方时返回 ''（调用方据此跳过发货并留存/提醒）。"""
    if not channel_name:
        return ""
    last = channel_name.strip().split("-")[-1].strip().upper()
    return last if last in ALL_COURIERS else ""


def courier_priority(shop_name: str) -> list:
    """（旧规则，2026-07-09 已弃用）曾按店铺返回快递方优先列表做 RM→DPD→EH 轮转重试。
    新规则改为「渠道末段 = 单一快递方」，见 channel_courier()。此函数保留仅作兼容/参考，勿再用于发货编排。"""
    if not shop_name:
        return list(DEFAULT_COURIER_ORDER)
    key = shop_name.strip()
    # 先精确，再包含匹配
    if key in COURIER_RULES:
        return list(COURIER_RULES[key])
    low = key.lower()
    for k, v in COURIER_RULES.items():
        if k.lower() in low or low in k.lower():
            return list(v)
    return list(DEFAULT_COURIER_ORDER)
