# -*- coding: utf-8 -*-
"""TK 整站采集 · 图形启动器（广告日报 + 夜间整站 + 规则飞书）"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from tkinter import (
    BOTH,
    DISABLED,
    END,
    LEFT,
    NORMAL,
    RIGHT,
    WORD,
    Button,
    Canvas,
    Frame,
    Label,
    Scrollbar,
    Text,
    Tk,
    messagebox,
)

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
LOGS = ROOT / "logs"
REPORTS = ROOT / "日报"
CONFIG = ROOT / "config" / "stores.config.json"
# collectors/tiktok-ads → 仓库根
REPO_ROOT = ROOT.parent.parent
REPO_SCRIPTS = REPO_ROOT / "scripts"
POWERSHELL = "powershell.exe"

# 与 install-*-daily-task / 调度划分计划一致（广告 17:20 不动）
T_AD = "17:20"
T_SHOP = "19:45"
T_FULL = "19:50"
T_ORDERS = "20:00"
T_PRODUCTS = "20:20"
T_CONTENT = "20:40"
T_AFFILIATE = "20:55"
T_POST = "21:00"


def _ps_file(script: Path, *extra: str) -> list[str]:
    cmd = [
        POWERSHELL,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
    ]
    cmd.extend(extra)
    return cmd


class App(Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("TK 整站采集 · 启动器")
        self.geometry("780x720")
        self.minsize(700, 600)
        self.configure(bg="#0f1419")
        self._proc: Optional[subprocess.Popen] = None
        self._q: queue.Queue[str] = queue.Queue()
        self._log_path: Optional[Path] = None
        self._build()
        self.after(100, self._drain_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        LOGS.mkdir(parents=True, exist_ok=True)

    def _build(self) -> None:
        header = Frame(self, bg="#1a222c", padx=16, pady=12)
        header.pack(fill="x")
        Label(
            header,
            text="TK 整站采集启动器",
            font=("Microsoft YaHei UI", 16, "bold"),
            fg="#f8fafc",
            bg="#1a222c",
        ).pack(anchor="w")
        Label(
            header,
            text=(
                f"广告 {T_AD}  ·  夜间整站 {T_SHOP}–{T_AFFILIATE}  ·  "
                f"规则+飞书 {T_POST}  ·  紫鸟串行 / PG 入库  ·  按钮区可滚轮下滑"
            ),
            font=("Microsoft YaHei UI", 10),
            fg="#cbd5e1",
            bg="#1a222c",
        ).pack(anchor="w", pady=(4, 0))

        # ---- fixed footer first (pack bottom) so log/status stay visible ----
        foot = Frame(self, bg="#0f1419", padx=16, pady=6)
        foot.pack(side="bottom", fill="x")
        Label(
            foot,
            text=f"{ROOT}  |  repo {REPO_ROOT.name}",
            font=("Segoe UI", 8),
            fg="#64748b",
            bg="#0f1419",
            anchor="w",
        ).pack(side=LEFT)

        # ---- status bar (above footer) ----
        status = Frame(self, bg="#0f1419", padx=16, pady=4)
        status.pack(side="bottom", fill="x")
        self.status_var = Label(
            status,
            text="就绪 · 广告先预览店铺；夜间链请确认紫鸟已登录 · 按钮区可滚轮",
            font=("Microsoft YaHei UI", 10),
            fg="#e2e8f0",
            bg="#0f1419",
            anchor="w",
        )
        self.status_var.pack(side=LEFT, fill="x", expand=True)

        # ---- log panel (bottom half, fixed min height) ----
        log_frame = Frame(self, bg="#1a222c", padx=8, pady=6)
        log_frame.pack(side="bottom", fill=BOTH, expand=False)
        log_frame.configure(height=180)
        log_frame.pack_propagate(False)
        Label(
            log_frame,
            text="运行输出",
            font=("Microsoft YaHei UI", 10, "bold"),
            fg="#f1f5f9",
            bg="#1a222c",
            anchor="w",
        ).pack(fill="x", padx=4, pady=(2, 4))
        text_wrap = Frame(log_frame, bg="#1a222c")
        text_wrap.pack(fill=BOTH, expand=True, padx=4, pady=(0, 4))
        log_scroll = Scrollbar(text_wrap)
        log_scroll.pack(side=RIGHT, fill="y")
        self.log = Text(
            text_wrap,
            wrap=WORD,
            font=("Consolas", 9),
            bg="#0b1220",
            fg="#e2e8f0",
            insertbackground="#e2e8f0",
            relief="flat",
            yscrollcommand=log_scroll.set,
            height=8,
        )
        self.log.pack(side=LEFT, fill=BOTH, expand=True)
        log_scroll.config(command=self.log.yview)

        # ---- scrollable button area (takes remaining space) ----
        btn_outer = Frame(self, bg="#0f1419", padx=12, pady=8)
        btn_outer.pack(fill=BOTH, expand=True)

        canvas = Canvas(btn_outer, bg="#0f1419", highlightthickness=0, bd=0)
        btn_scroll = Scrollbar(btn_outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=btn_scroll.set)
        btn_scroll.pack(side=RIGHT, fill="y")
        canvas.pack(side=LEFT, fill=BOTH, expand=True)

        grid = Frame(canvas, bg="#0f1419")
        win_id = canvas.create_window((0, 0), window=grid, anchor="nw")

        def _on_grid_configure(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event) -> None:  # type: ignore[no-untyped-def]
            canvas.itemconfigure(win_id, width=event.width)

        grid.bind("<Configure>", _on_grid_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event) -> None:  # type: ignore[no-untyped-def]
            # Windows: event.delta is ±120
            if event.delta:
                canvas.yview_scroll(int(-event.delta / 120), "units")

        def _bind_wheel_tree(widget) -> None:  # type: ignore[no-untyped-def]
            # Bind on every child so hover-over-button still scrolls
            # (parent Leave would unbind_all if we used Enter/Leave only).
            widget.bind("<MouseWheel>", _on_mousewheel)
            for child in widget.winfo_children():
                _bind_wheel_tree(child)

        # (section_title|None, button_text, command, color)
        items: list[tuple[Optional[str], str, Callable[[], None], str]] = [
            ("广告日报（同事机常见 · 17:20）", "广告·预览店铺", self.run_ads_list, "#3b82f6"),
            (None, "广告·干跑(不写飞书)", self.run_ads_dry, "#64748b"),
            (None, f"广告·立即日报 {T_AD}", self.run_ads_daily, "#0ea5e9"),
            (None, f"广告·安装 {T_AD} 任务", self.install_ads_task, "#8b5cf6"),
            ("夜间整站 · 立即跑（需紫鸟）", "整站·店KPI/健康/财务", self.run_shop, "#2563eb"),
            (None, "整站·订单", self.run_orders, "#2563eb"),
            (None, "整站·商品", self.run_products, "#2563eb"),
            (None, "整站·内容+商品卡", self.run_content, "#0891b2"),
            (None, "整站·联盟达人", self.run_affiliate, "#0891b2"),
            (None, "整站·合并链 full-site", self.run_full_site, "#0284c7"),
            ("中心尾巴 · 不抢紫鸟", f"规则+飞书 {T_POST}", self.run_post_collect, "#16a34a"),
            (None, "飞书·仅同步(全量)", self.run_feishu_sync, "#15803d"),
            ("安装计划任务", "安装·夜间拆分任务包", self.install_night_split, "#a855f7"),
            (None, f"安装·{T_POST} 规则飞书", self.install_post_task, "#9333ea"),
            ("其它", "白天·空闲轮巡(SkipAds)", self.run_day_loop, "#d97706"),
            (None, "打开日志目录", self.open_logs, "#475569"),
            (None, "打开配置 / 日报", self.open_config_reports, "#475569"),
            (None, "环境自检", self.doctor_only, "#f59e0b"),
            (None, "安装环境依赖", self.install_deps, "#f59e0b"),
            (None, "停止当前任务", self.stop_proc, "#dc2626"),
        ]

        row = 0
        col = 0
        for section, text, cmd, color in items:
            if section:
                if col == 1:
                    row += 1
                    col = 0
                sec = Frame(grid, bg="#243044", padx=10, pady=5)
                sec.grid(row=row, column=0, columnspan=2, sticky="ew", padx=4, pady=(12, 4))
                Label(
                    sec,
                    text="▍ " + section,
                    font=("Microsoft YaHei UI", 10, "bold"),
                    fg="#f1f5f9",
                    bg="#243044",
                    anchor="w",
                ).pack(fill="x")
                row += 1
                col = 0
            b = Button(
                grid,
                text=text,
                command=cmd,
                font=("Microsoft YaHei UI", 10),
                fg="#ffffff",
                bg=color,
                activebackground=color,
                activeforeground="#ffffff",
                relief="flat",
                cursor="hand2",
                padx=8,
                pady=8,
            )
            b.grid(row=row, column=col, sticky="ew", padx=4, pady=3)
            col += 1
            if col >= 2:
                col = 0
                row += 1

        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        # After buttons exist, wire wheel on canvas + whole button tree
        _bind_wheel_tree(canvas)
        _bind_wheel_tree(grid)

    def _append(self, line: str) -> None:
        self.log.configure(state=NORMAL)
        self.log.insert(END, line + "\n")
        self.log.see(END)
        self.log.configure(state=DISABLED)

    def _new_run_log_path(self, title: str) -> Path:
        LOGS.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:40]
        return LOGS / f"gui-{stamp}-{safe}.log"

    def _set_status(self, text: str) -> None:
        self.status_var.configure(text=text)

    def _drain_queue(self) -> None:
        try:
            while True:
                line = self._q.get_nowait()
                self._append(line)
        except queue.Empty:
            pass
        self.after(100, self._drain_queue)

    def _busy(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @staticmethod
    def _bridge_hint(text: str) -> Optional[str]:
        markers = (
            "127.0.0.1:9481",
            "bridge",
            "无法连接",
            "连不上",
            "store list failed",
            "Bridge down",
        )
        low = text.lower()
        if any(m in text or m in low for m in markers):
            return (
                "无法连接紫鸟 Bridge（本机 127.0.0.1:9481）。\n\n"
                "请按顺序检查：\n"
                "1. 已安装并打开「紫鸟」桌面客户端\n"
                "2. 已登录（不要只开着托盘图标未登录）\n"
                "3. 等客户端完全启动后再点预览/采集\n"
                "4. 启动器点「环境自检」确认 ziniao-cli 正常\n\n"
                "说明：仅装 Node / ziniao-cli 不够，必须本机紫鸟客户端在线。"
            )
        return None

    def _on_task_done(self, title: str, code: int, collected: str, log_path: Path) -> None:
        self._log_path = log_path
        self._set_status(f"完成：{title} (exit={code}) · 日志 {log_path.name}")
        if code == 0:
            return
        hint = self._bridge_hint(collected)
        if hint:
            messagebox.showerror("紫鸟未连接", hint)
        else:
            messagebox.showwarning(
                "任务失败",
                f"{title} 失败 (exit={code})。\n\n完整输出已写入：\n{log_path}\n\n"
                "可点「打开日志目录」把该文件发给运维。",
            )

    def _run(
        self,
        title: str,
        cmd: list[str],
        confirm: str | None = None,
        cwd: Path | None = None,
    ) -> None:
        if self._busy():
            messagebox.showwarning("进行中", "已有任务在运行，请先「停止当前任务」或等待结束。")
            return
        if confirm and not messagebox.askyesno("确认", confirm):
            return
        if "-File" in cmd:
            idx = cmd.index("-File") + 1
            if idx < len(cmd) and not Path(cmd[idx]).exists():
                messagebox.showerror("错误", f"脚本不存在:\n{cmd[idx]}")
                return

        workdir = cwd or ROOT
        log_path = self._new_run_log_path(title)
        self._log_path = log_path
        header = [
            "",
            f"======== {datetime.now():%H:%M:%S} {title} ========",
            f"cwd={workdir}",
            " ".join(cmd),
            f"[log] {log_path}",
        ]
        for h in header:
            self._append(h)

        self._set_status(f"运行中：{title} · 日志 {log_path.name}")

        def worker() -> None:
            collected: list[str] = []
            try:
                with open(log_path, "w", encoding="utf-8", newline="\n") as fp:

                    def emit(s: str) -> None:
                        collected.append(s)
                        self._q.put(s)
                        try:
                            fp.write(s + "\n")
                            fp.flush()
                        except Exception:  # noqa: BLE001
                            pass

                    for h in header:
                        try:
                            fp.write(h + "\n")
                        except Exception:  # noqa: BLE001
                            pass
                    fp.flush()

                    creation = 0
                    if sys.platform == "win32":
                        creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    self._proc = subprocess.Popen(
                        cmd,
                        cwd=str(workdir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        creationflags=creation,
                    )
                    assert self._proc.stdout is not None
                    for line in self._proc.stdout:
                        emit(line.rstrip("\r\n"))
                    code = self._proc.wait()
                    emit(f"--- 结束 exit={code} ---")
                    emit(f"[log] saved: {log_path}")
                    blob = "\n".join(collected)
                    self.after(
                        0,
                        lambda c=code, b=blob, p=log_path: self._on_task_done(title, c, b, p),
                    )
            except Exception as e:  # noqa: BLE001
                self._q.put(f"ERROR: {e}")
                self._q.put(f"[log] saved: {log_path}")
                try:
                    with open(log_path, "a", encoding="utf-8") as fp:
                        fp.write(f"ERROR: {e}\n")
                except Exception:  # noqa: BLE001
                    pass
                self.after(0, lambda: self._set_status(f"失败：{title} · 见 {log_path.name}"))
            finally:
                self._proc = None

        threading.Thread(target=worker, daemon=True).start()

    def _run_chain(self, title: str, steps: list[tuple[str, list[str], Path]], confirm: str) -> None:
        """Run multiple PowerShell installs sequentially in one worker."""
        if self._busy():
            messagebox.showwarning("进行中", "已有任务在运行，请先「停止当前任务」或等待结束。")
            return
        if not messagebox.askyesno("确认", confirm):
            return
        for _name, cmd, _cwd in steps:
            if "-File" in cmd:
                idx = cmd.index("-File") + 1
                if idx < len(cmd) and not Path(cmd[idx]).exists():
                    messagebox.showerror("错误", f"脚本不存在:\n{cmd[idx]}")
                    return

        log_path = self._new_run_log_path(title)
        self._log_path = log_path
        self._append("")
        self._append(f"======== {datetime.now():%H:%M:%S} {title} ========")
        self._set_status(f"运行中：{title} · 日志 {log_path.name}")

        def worker() -> None:
            collected: list[str] = []
            final_code = 0
            try:
                with open(log_path, "w", encoding="utf-8", newline="\n") as fp:

                    def emit(s: str) -> None:
                        collected.append(s)
                        self._q.put(s)
                        try:
                            fp.write(s + "\n")
                            fp.flush()
                        except Exception:  # noqa: BLE001
                            pass

                    creation = 0
                    if sys.platform == "win32":
                        creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)

                    for step_name, cmd, cwd in steps:
                        emit(f"----- {step_name} -----")
                        emit(" ".join(cmd))
                        self._proc = subprocess.Popen(
                            cmd,
                            cwd=str(cwd),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            creationflags=creation,
                        )
                        assert self._proc.stdout is not None
                        for line in self._proc.stdout:
                            emit(line.rstrip("\r\n"))
                        code = self._proc.wait()
                        emit(f"--- {step_name} exit={code} ---")
                        if code != 0:
                            final_code = code
                    emit(f"--- 链结束 final_exit={final_code} ---")
                    emit(f"[log] saved: {log_path}")
                    blob = "\n".join(collected)
                    self.after(
                        0,
                        lambda c=final_code, b=blob, p=log_path: self._on_task_done(
                            title, c, b, p
                        ),
                    )
            except Exception as e:  # noqa: BLE001
                self._q.put(f"ERROR: {e}")
                self.after(0, lambda: self._set_status(f"失败：{title}"))
            finally:
                self._proc = None

        threading.Thread(target=worker, daemon=True).start()

    # ----- 广告 -----
    def run_ads_list(self) -> None:
        self._run("广告·预览店铺", _ps_file(SCRIPTS / "run-multi-store.ps1", "-ListOnly"))

    def run_ads_dry(self) -> None:
        self._run(
            "广告·干跑",
            _ps_file(SCRIPTS / "run-multi-store.ps1", "-DryRun", "true"),
            confirm="将串行打开紫鸟抓广告（不写飞书）。\n确认紫鸟已登录？",
        )

    def run_ads_daily(self) -> None:
        self._run(
            "广告·立即日报",
            _ps_file(SCRIPTS / "run-daily-report.ps1"),
            confirm=f"执行与 {T_AD} 计划任务相同的广告日报（写飞书）。\n继续？",
        )

    def install_ads_task(self) -> None:
        self._run(
            f"安装广告 {T_AD} 任务",
            _ps_file(SCRIPTS / "install-daily-task.ps1", "-Time", T_AD),
            confirm=f"安装/更新 TK-Ad-Daily-Report（每天 {T_AD}）。\n继续？",
        )

    # ----- 整站立即跑 -----
    def run_shop(self) -> None:
        self._run(
            "整站·店模块",
            _ps_file(SCRIPTS / "run-shop-modules-daily.ps1"),
            confirm="立即跑店 KPI/健康/财务 → 清泉 Ingest。\n需紫鸟。继续？",
        )

    def run_orders(self) -> None:
        self._run(
            "整站·订单",
            _ps_file(SCRIPTS / "run-orders-daily.ps1"),
            confirm="立即跑订单全店 → Ingest。需紫鸟。继续？",
        )

    def run_products(self) -> None:
        self._run(
            "整站·商品",
            _ps_file(SCRIPTS / "run-products-daily.ps1"),
            confirm="立即跑商品全店 → Ingest。需紫鸟。继续？",
        )

    def run_content(self) -> None:
        self._run(
            "整站·内容",
            _ps_file(SCRIPTS / "run-content-daily.ps1"),
            confirm="立即跑视频+商品卡（强制入库）。需紫鸟。继续？",
        )

    def run_affiliate(self) -> None:
        self._run(
            "整站·达人",
            _ps_file(SCRIPTS / "run-affiliate-daily.ps1"),
            confirm="立即跑联盟达人（强制入库，含 Pop）。\n投流/寄样不填 0。需紫鸟。继续？",
        )

    def run_full_site(self) -> None:
        self._run(
            "整站·full-site",
            _ps_file(SCRIPTS / "run-full-site-daily.ps1"),
            confirm=(
                "合并链：shop → orders → products（不含广告）。\n"
                "勿与拆分日更同时高峰双开。需紫鸟。继续？"
            ),
        )

    def run_post_collect(self) -> None:
        script = REPO_SCRIPTS / "tk-p0-post-collect.ps1"
        self._run(
            "规则+飞书",
            _ps_file(script, "-LookbackDays", "14"),
            confirm=(
                f"跑规则（ads/product/shop/content/affiliate）+ 飞书 T1/T2/T6/T7/异常。\n"
                f"不需要紫鸟；需本机可连 PG 与飞书。\n"
                f"定时默认 {T_POST}。继续？"
            ),
            cwd=REPO_ROOT,
        )

    def run_feishu_sync(self) -> None:
        script = REPO_SCRIPTS / "feishu-tk-daily-sync.ps1"
        self._run(
            "飞书全量同步",
            _ps_file(script, "-LookbackDays", "14"),
            confirm="仅 PG→飞书同步（不含规则扫单）。需 FEISHU_* 与库连接。继续？",
            cwd=REPO_ROOT,
        )

    def run_day_loop(self) -> None:
        self._run(
            "白天空闲轮巡",
            _ps_file(
                SCRIPTS / "night-loop.ps1",
                "-SkipAds",
                "-IntervalSec",
                "1800",
            ),
            confirm=(
                "启动空闲轮巡：SkipAds，默认 30 分钟一轮（orders/products/shop）。\n"
                "会一直跑直到你点「停止」或关窗口。\n"
                f"请勿在 {T_AD} 前后与广告抢紫鸟；建议 09:00–16:50 使用。\n继续？"
            ),
        )

    # ----- 安装任务 -----
    def install_night_split(self) -> None:
        steps = [
            (
                f"shop {T_SHOP}",
                _ps_file(SCRIPTS / "install-shop-modules-daily-task.ps1", "-Time", T_SHOP),
                ROOT,
            ),
            (
                f"orders {T_ORDERS}",
                _ps_file(SCRIPTS / "install-orders-daily-task.ps1", "-Time", T_ORDERS),
                ROOT,
            ),
            (
                f"products {T_PRODUCTS}",
                _ps_file(SCRIPTS / "install-products-daily-task.ps1", "-Time", T_PRODUCTS),
                ROOT,
            ),
            (
                f"content {T_CONTENT}",
                _ps_file(SCRIPTS / "install-content-daily-task.ps1", "-Time", T_CONTENT),
                ROOT,
            ),
            (
                f"affiliate {T_AFFILIATE}",
                _ps_file(SCRIPTS / "install-affiliate-daily-task.ps1", "-Time", T_AFFILIATE),
                ROOT,
            ),
        ]
        self._run_chain(
            "安装夜间拆分任务包",
            steps,
            confirm=(
                "将安装/更新计划任务：\n"
                f"  Shop {T_SHOP} · Orders {T_ORDERS} · Products {T_PRODUCTS}\n"
                f"  Content {T_CONTENT} · Affiliate {T_AFFILIATE}\n\n"
                f"不含广告 {T_AD}（请单独装）。\n"
                f"不含 {T_POST} 规则飞书（中心机另装）。\n"
                "勿与 TK-Full-Site-Daily 同时开。\n继续？"
            ),
        )

    def install_post_task(self) -> None:
        script = REPO_SCRIPTS / "install-tk-p0-post-collect-daily-task.ps1"
        self._run(
            f"安装 {T_POST} 尾巴",
            _ps_file(script, "-Time", T_POST),
            confirm=(
                f"安装 TK-P0-Post-Collect-Daily（每天 {T_POST}）。\n"
                "机器需能连 PostgreSQL + 飞书，不需要紫鸟。\n继续？"
            ),
            cwd=REPO_ROOT,
        )

    def install_deps(self) -> None:
        self._run(
            "安装环境依赖",
            _ps_file(SCRIPTS / "install-deps.ps1"),
            confirm=(
                "将检查/安装 Node.js LTS、ziniao-cli 等。\n"
                "不含紫鸟桌面客户端。继续？"
            ),
        )

    def doctor_only(self) -> None:
        self._run("环境自检", _ps_file(SCRIPTS / "install-deps.ps1", "-DoctorOnly"))

    def open_logs(self) -> None:
        LOGS.mkdir(parents=True, exist_ok=True)
        os.startfile(str(LOGS))  # type: ignore[attr-defined]
        self._set_status("已打开日志目录")

    def open_config_reports(self) -> None:
        REPORTS.mkdir(parents=True, exist_ok=True)
        if CONFIG.exists():
            os.startfile(str(CONFIG))  # type: ignore[attr-defined]
        else:
            example = ROOT / "config" / "stores.config.example.json"
            messagebox.showinfo(
                "配置",
                f"未找到 stores.config.json\n请复制:\n{example}\n为 stores.config.json。",
            )
            if example.parent.exists():
                os.startfile(str(example.parent))  # type: ignore[attr-defined]
        os.startfile(str(REPORTS))  # type: ignore[attr-defined]
        self._set_status("已打开配置 / 日报目录")

    def stop_proc(self) -> None:
        if not self._busy() or self._proc is None:
            messagebox.showinfo("停止", "当前没有运行中的任务。")
            return
        try:
            self._proc.terminate()
            self._append("--- 已请求停止 ---")
            self._set_status("已停止")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("停止失败", str(e))

    def _on_close(self) -> None:
        if self._busy():
            if not messagebox.askyesno("退出", "任务仍在运行，确定退出？"):
                return
            try:
                if self._proc:
                    self._proc.terminate()
            except Exception:  # noqa: BLE001
                pass
        self.destroy()


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
