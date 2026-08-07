# -*- coding: utf-8 -*-
"""飞书连通测试：读取 g2-3shops 配置，发一条美化卡片。"""
import argparse
import sys
import time

import yaml

from bridge.notify import Notifier


def main():
    ap = argparse.ArgumentParser(description="飞书卡片连通测试")
    ap.add_argument(
        "--config",
        default="config/config.g2-3shops.yaml",
        help="配置文件路径",
    )
    ap.add_argument(
        "--demo",
        choices=["test", "high", "medium", "all"],
        default="test",
        help="test=连通卡 / high=严重对账样例 / medium=关注样例 / all=三张都发",
    )
    args = ap.parse_args()

    try:
        with open(args.config, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"读取配置失败: {args.config}\n{e}")
        return 1

    notify = cfg.get("notify") or {}
    webhook = (notify.get("feishu_webhook") or "").strip()
    customer = (cfg.get("customer") or {}).get("name") or "test"

    print(f"配置: {args.config}")
    print(f"客户: {customer}")
    print(f"演示: {args.demo}")
    if not webhook:
        print("失败: config 中 notify.feishu_webhook 为空，未配置飞书机器人。")
        print(f"请在 {args.config} 的 notify.feishu_webhook 填入群机器人 webhook。")
        return 2

    shown = webhook if len(webhook) < 40 else webhook[:28] + "..." + webhook[-8:]
    print(f"webhook: {shown}")

    n = Notifier(webhook, customer)
    modes = ["test", "high", "medium"] if args.demo == "all" else [args.demo]
    ok_all = True

    for i, mode in enumerate(modes):
        if i:
            time.sleep(1.2)  # 飞书自定义机器人约 5 次/秒、100 次/分，连发易 11232
        if mode == "test":
            ok = n.test("飞书卡片美化连通测试（来自启动器/test_feishu.py）")
        elif mode == "high":
            ok = n.recon_alert(
                total=427,
                days=7,
                highs=[
                    {
                        "detail": (
                            "P2AM6TCD63152 双边运单号不一致："
                            "赛狐 GV723197296GB ≠ WMS GV723200361GB（承运 RM）"
                        ),
                    },
                    {
                        "detail": (
                            "P2AM6TCD63154 双边运单号不一致："
                            "赛狐 GV723197526GB ≠ WMS GV723200375GB（承运 RM）"
                        ),
                    },
                ],
                mediums=[
                    {"detail": "PXXX 赛狐已发货但无 submitTime——疑似漏提交平台"},
                ],
                summary={
                    "OK": 424,
                    "TRACKING_MISMATCH": 2,
                    "SELLFOX_NOT_SUBMITTED": 1,
                },
            )
        else:  # medium
            ok = n.recon_alert(
                total=436,
                days=7,
                highs=[],
                mediums=[
                    {"detail": "PAAA 赛狐已发货但无 submitTime——疑似漏提交平台"},
                    {"detail": "PBBB 赛狐已发货但无 submitTime——疑似漏提交平台"},
                ],
                summary={"OK": 434, "SELLFOX_NOT_SUBMITTED": 2},
            )
        print(f"  [{mode}] {'成功' if ok else '失败'}")
        ok_all = ok_all and ok

    if ok_all:
        print("发送成功：请到飞书群查看卡片样式。")
        return 0
    print("发送失败：请查看上方错误或 bridge 日志（网络/webhook 失效/签名校验等）。")
    return 3


if __name__ == "__main__":
    code = main()
    print()
    if sys.platform == "win32":
        try:
            input("按回车关闭…")
        except EOFError:
            pass
    sys.exit(code)
