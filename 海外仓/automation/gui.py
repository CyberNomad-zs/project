# -*- coding: utf-8 -*-
"""
海外仓发货自动化 · 图形启动器（Tkinter，Python 自带，无新依赖）。
等价于 启动.bat，但是一个真正的窗口 + 彩色按钮：
  · 绿色=安全（空跑/只读）   · 红色=真跑（真实下单/发货/确认，不可逆）   · 蓝色=工具
点任一按钮 → 在【新的控制台窗口】里跑对应脚本，日志照旧滚动、Ctrl+C 照旧能停。
真跑类按钮会弹窗要求输入大写 YES 二次确认（等同 启动.bat 的红字确认）。

启动：双击『美化启动器.bat』，或命令行  pythonw gui.py / python gui.py
"""
import os
import sys
import shutil
import subprocess
import tkinter as tk
from tkinter import font as tkfont
from tkinter import simpledialog, messagebox

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")

# 国内镜像（与 启动.bat [8] 一致）
PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
PW_MIRROR = "https://cdn.npmmirror.com/binaries/playwright"


def detect_py():
    """选一个能用的 Python 调用方式（子进程里用），优先 python，其次 py，最后当前解释器全路径。"""
    if shutil.which("python"):
        return "python"
    if shutil.which("py"):
        return "py -3.12"
    return f'"{sys.executable}"'


PY = detect_py()

# key -> (在新控制台里执行的 cmd 命令模板, 需二次确认的 key 或 None)
# 说明：set HWC_DRY_RUN=0 => 真跑；=1 => 空跑。config.py 读取时会 strip，故写不写空格都安全。
TEMPLATES = {
    "dryrun":    ("title HWC-dryrun&& set HWC_DRY_RUN=1&& {PY} run_shipping.py", None),
    "login":     ("title HWC-login&& {PY} capture\\erp_manual_login.py", None),
    "login_real":("title HWC-login+real&& {PY} capture\\erp_manual_login.py&& set HWC_DRY_RUN=0&& {PY} run_shipping.py", "login_real"),
    "realrun":   ("title HWC-realrun&& set HWC_DRY_RUN=0&& {PY} run_shipping.py", "realrun"),
    "fullloop":  ("title HWC-fullloop&& set HWC_DRY_RUN=0&& {PY} full_loop.py", "fullloop"),
    "shiploop":  ("title HWC-shiploop&& set HWC_DRY_RUN=0&& {PY} shipping_loop.py", "shiploop"),
    "trackloop": ("title HWC-trackloop&& {PY} status_update_loop.py", None),
    "deps":      ("title HWC-deps&& {PY} -m pip install -r requirements.txt -i " + PIP_MIRROR
                  + "&& set PLAYWRIGHT_DOWNLOAD_HOST=" + PW_MIRROR + "&& {PY} -m playwright install chromium", None),
    "feishu":    ("title HWC-feishu&& {PY} notify.py", None),
    "clearcache":("title HWC-clearcache&& powershell -NoProfile -ExecutionPolicy Bypass -File clear_cache.ps1", None),
}

CONFIRM_MSG = {
    "login_real": "登录 ERP 后立即【真实发货】：下单 + 发货 + 拉跟踪号 + 确认发货。",
    "realrun":    "【真实发货】：下单 + 发货 + 拉跟踪号 + 确认发货。",
    "shiploop":   "启动【发货循环】：每 5 分钟真实 下单 + 发货，一直循环（Ctrl+C 停）。",
    "fullloop":   "启动【全流程循环】：每 30 分钟真实 下单 + 发货 + 拉跟踪号 +\n确认发货（扣库存 / 提交平台，不可逆），一直循环（Ctrl+C 停）。",
}


def build_inner(key):
    """把模板里的 {PY} 填好，得到最终在新控制台执行的命令串。"""
    tmpl, _ = TEMPLATES[key]
    return tmpl.format(PY=PY)


def launch_console(inner):
    """在一个【新的控制台窗口】里执行 inner（cmd /k 会执行完保留窗口，便于看结果/续输入）。"""
    # cmd /k "<inner>"：inner 内含 & 等特殊字符，cmd 会剥掉我加的这对外层引号(规则2)，命令原样执行。
    subprocess.Popen(f'cmd /k "{inner}"',
                     creationflags=subprocess.CREATE_NEW_CONSOLE, cwd=BASE_DIR)


class App:
    def __init__(self, root):
        self.root = root
        root.title("海外仓发货 · 自动化启动器")
        root.configure(bg="#f4f6f8")
        root.minsize(430, 560)
        try:
            root.tk.call("tk", "scaling", 1.15)
        except Exception:
            pass

        self.f_title = tkfont.Font(family="Microsoft YaHei UI", size=15, weight="bold")
        self.f_sub = tkfont.Font(family="Microsoft YaHei UI", size=9)
        self.f_sec = tkfont.Font(family="Microsoft YaHei UI", size=10, weight="bold")
        self.f_btn = tkfont.Font(family="Microsoft YaHei UI", size=11)
        self.f_status = tkfont.Font(family="Microsoft YaHei UI", size=9)

        # ---- 顶部横幅 ----
        head = tk.Frame(root, bg="#1f6feb")
        head.pack(fill="x")
        tk.Label(head, text="海外仓发货 · 自动化", bg="#1f6feb", fg="white",
                 font=self.f_title).pack(anchor="w", padx=16, pady=(12, 0))
        tk.Label(head, text="绿=安全 · 红=真跑(不可逆) · 蓝=工具　　点按钮在新窗口运行",
                 bg="#1f6feb", fg="#d7e6ff", font=self.f_sub).pack(anchor="w", padx=16, pady=(2, 12))

        body = tk.Frame(root, bg="#f4f6f8")
        body.pack(fill="both", expand=True, padx=14, pady=10)

        # ---- ① 核对 ----
        s1 = self._section(body, "① 核对（安全，第一次先跑这个）")
        self._btn(s1, "空跑核对", "safe", lambda: self.handle("dryrun"),
                  full=True, hint="不真下单/发货，只走筛选·统计·定位")

        # ---- ② 登录 / 真实发货 ----
        s2 = self._section(body, "② 登录 / 真实发货")
        self._btn(s2, "登录 ERP", "neutral", lambda: self.handle("login"), col=0,
                  hint="手动过滑块")
        self._btn(s2, "真实发货", "danger", lambda: self.handle("realrun"), col=1,
                  hint="已登录时用")
        self._btn(s2, "登录 + 真实发货", "danger", lambda: self.handle("login_real"),
                  full=True, hint="推荐真跑：先登录再一步到位")

        # ---- ③ 常驻循环 ----
        s3 = self._section(body, "③ 常驻循环（Ctrl+C 停）")
        self._btn(s3, "全流程循环 · 每30分", "danger", lambda: self.handle("fullloop"),
                  full=True, hint="下单+发货+拉跟踪号+确认发货，一条龙")
        self._btn(s3, "发货循环 · 每5分", "danger", lambda: self.handle("shiploop"), col=0,
                  hint="只下单+发货")
        self._btn(s3, "跟踪号循环 · 每10分", "safe", lambda: self.handle("trackloop"), col=1,
                  hint="只拉单号，只读安全")

        # ---- ④ 工具 ----
        s4 = self._section(body, "④ 工具")
        self._btn(s4, "查看日志", "tool", lambda: self.handle("logs"), col=0)
        self._btn(s4, "安装 / 更新依赖", "tool", lambda: self.handle("deps"), col=1)
        self._btn(s4, "清理浏览器缓存", "tool", lambda: self.handle("clearcache"), col=0)
        self._btn(s4, "测试飞书", "tool", lambda: self.handle("feishu"), col=1)

        # ---- 状态栏 ----
        self.status = tk.StringVar(value="就绪　·　目录: " + BASE_DIR)
        tk.Label(root, textvariable=self.status, bg="#e9edf1", fg="#444",
                 font=self.f_status, anchor="w").pack(fill="x", side="bottom", ipady=4)

    # ---------- UI helpers ----------
    def _section(self, parent, title):
        wrap = tk.Frame(parent, bg="#f4f6f8")
        wrap.pack(fill="x", pady=(4, 8))
        tk.Label(wrap, text=title, bg="#f4f6f8", fg="#333",
                 font=self.f_sec, anchor="w").pack(fill="x", pady=(0, 4))
        grid = tk.Frame(wrap, bg="#f4f6f8")
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=1, uniform="c")
        grid.columnconfigure(1, weight=1, uniform="c")
        grid._row = 0
        grid._col = 0
        return grid

    _COLORS = {
        "safe":    ("#2e9e5b", "#268a4f"),
        "danger":  ("#d64545", "#c23b3b"),
        "tool":    ("#3b7dd8", "#356fc2"),
        "neutral": ("#6b7280", "#5c626b"),
    }

    def _btn(self, grid, text, kind, cmd, col=None, full=False, hint=None):
        bg, abg = self._COLORS[kind]
        label = text if not hint else f"{text}\n{hint}"
        b = tk.Button(grid, text=label, command=cmd, bg=bg, fg="white",
                      activebackground=abg, activeforeground="white",
                      font=self.f_btn, relief="flat", bd=0, cursor="hand2",
                      justify="center", pady=8)
        if full:
            b.grid(row=grid._row, column=0, columnspan=2, sticky="ew", padx=3, pady=3)
            grid._row += 1
            grid._col = 0
        else:
            c = grid._col if col is None else col
            b.grid(row=grid._row, column=c, sticky="ew", padx=3, pady=3)
            if c == 1:
                grid._row += 1
                grid._col = 0
            else:
                grid._col = 1

    # ---------- 动作 ----------
    def handle(self, key):
        if key == "logs":
            os.makedirs(LOG_DIR, exist_ok=True)
            try:
                os.startfile(LOG_DIR)
            except Exception as e:
                messagebox.showerror("打开日志失败", str(e))
            self.status.set("已打开日志文件夹")
            return

        confirm_key = TEMPLATES[key][1]
        if confirm_key:
            if not self._confirm_real(CONFIRM_MSG[confirm_key]):
                self.status.set("已取消（未确认）")
                return
        launch_console(build_inner(key))
        self.status.set(f"已在新窗口启动：{key}")

    def _confirm_real(self, desc):
        v = simpledialog.askstring(
            "二次确认 · 真实操作",
            desc + "\n\n以上为真实、可能不可逆的操作。\n确认请输入大写  YES  ：",
            parent=self.root)
        return (v or "").strip() == "YES"


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
