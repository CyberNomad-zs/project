# -*- coding: utf-8 -*-
"""
temu-monitor · 图形启动器（Tkinter，Python 自带，无新依赖）。
仿 sellfox-bridge / automation 美化启动器：绿=安全 · 红=真跑 · 蓝=工具
点按钮 → 新控制台窗口执行。

启动：双击「美化启动器.bat」，或  pythonw gui.py / python gui.py
"""
import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
DATA_DIR = os.path.join(BASE_DIR, "data")

PY312 = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "Programs", "Python", "Python312", "python.exe",
)


def _short_path(path):
    """8.3 short path — avoids cmd nested-quote breakage on 'Program Files'."""
    if not path or " " not in path:
        return path
    try:
        import ctypes
        from ctypes import wintypes

        GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
        GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        GetShortPathNameW.restype = wintypes.DWORD
        buf = ctypes.create_unicode_buffer(512)
        if GetShortPathNameW(path, buf, 512):
            return buf.value or path
    except Exception:
        pass
    return path


def detect_node():
    """Node 可执行文件，供塞进 cmd 命令行。

    优先返回裸名 ``node``（新控制台继承 PATH），避免
    ``"C:\\Program Files\\nodejs\\node.EXE"`` 被 ``cmd /k`` + list2cmdline
    双重引号拆坏，报「不是内部或外部命令」。
    """
    if shutil.which("node"):
        return "node"
    for c in (
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "nodejs", "node.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "nodejs", "node.exe"),
    ):
        if os.path.isfile(c):
            return _short_path(c)
    return "node"


NODE = detect_node()


def detect_py():
    if os.path.isfile(PY312):
        return _short_path(PY312)
    if shutil.which("python"):
        return "python"
    if shutil.which("py"):
        return "py -3.12"
    return _short_path(sys.executable) if " " in (sys.executable or "") else (sys.executable or "python")


# key -> (cmd 模板, 二次确认 key 或 None)
# 不用 str.format：路径/JSON 花括号会炸。用 {NODE} 占位 replace。
TEMPLATES = {
    "login": (
        "title TemuMon-login&& {NODE} src\\cli.js login&& echo.&& pause",
        "login",
    ),
    "once": (
        "title TemuMon-once&& {NODE} src\\cli.js once&& echo.&& pause",
        None,
    ),
    "start": (
        "title TemuMon-start&& echo Keep this window open. Ctrl+C to stop.&& {NODE} src\\cli.js start",
        "start_fg",
    ),
    "start_bg": (
        "title TemuMon-daemon&& powershell -NoProfile -ExecutionPolicy Bypass -File run-forever.ps1",
        "start_bg",
    ),
    "install_auto": (
        "title TemuMon-autostart&& powershell -NoProfile -ExecutionPolicy Bypass -File install-autostart.ps1&& echo.&& pause",
        None,
    ),
    "uninstall_auto": (
        "title TemuMon-unauto&& powershell -NoProfile -ExecutionPolicy Bypass -File uninstall-autostart.ps1&& echo.&& pause",
        None,
    ),
    # 赛狐上下架只在服务器跑，本机启动器不再提供入口（避免同事误点）
    "deps": (
        "title TemuMon-deps&& npm install&& echo.&& pause",
        None,
    ),
}

CONFIRM_MSG = {
    "login": (
        "【登录 Temu · 监测专用】\n"
        "会打开监测自己的 Chrome 档案（.userdata），\n"
        "不是你日常上网的那个浏览器。\n\n"
        "若「流量常驻/守护」正在跑：请先关掉再登录，\n"
        "否则会把正在扫描的浏览器挤崩。\n\n"
        "只是想进后台人工改商品：用日常 Chrome 打开即可，\n"
        "不必点这个按钮。"
    ),
    "start_fg": (
        "【流量常驻 · 前台窗口】\n"
        "每 15 分钟：浏览器流量待关注 / 下降 / 在售。\n"
        "本机不跑上下架（服务器负责）。\n"
        "关闭窗口即停止。需要后台请用「开机自启」或守护脚本。\n"
        "常驻期间可用日常 Chrome 进 Temu；不要再点「登录 Temu」。"
    ),
    "start_bg": (
        "【守护进程 run-forever.ps1 · 仅流量】\n"
        "会开一个黑窗，里面应滚动显示监测日志（不是空白）。\n"
        "崩溃 30 秒自动重启；日志同时在 logs\\ 目录。\n"
        "勿与「流量常驻·前台」或第二个守护双开（会抢浏览器）。\n"
        "常驻期间可用日常 Chrome 进 Temu；不要再点「登录 Temu」。\n"
        "不会请求赛狐 API。"
    ),
}


def build_inner(key):
    tmpl, _ = TEMPLATES[key]
    return tmpl.replace("{NODE}", NODE)


def launch_console(inner):
    subprocess.Popen(
        ["cmd", "/k", inner],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        cwd=BASE_DIR,
    )


class App:
    def __init__(self, root):
        self.root = root
        root.title("temu-monitor · 本机流量监测")
        root.configure(bg="#f4f6f8")
        root.minsize(460, 420)
        root.geometry("520x580")
        try:
            root.tk.call("tk", "scaling", 1.15)
        except Exception:
            pass

        self.f_title = tkfont.Font(family="Microsoft YaHei UI", size=15, weight="bold")
        self.f_sub = tkfont.Font(family="Microsoft YaHei UI", size=9)
        self.f_sec = tkfont.Font(family="Microsoft YaHei UI", size=10, weight="bold")
        self.f_btn = tkfont.Font(family="Microsoft YaHei UI", size=11)
        self.f_status = tkfont.Font(family="Microsoft YaHei UI", size=9)

        head = tk.Frame(root, bg="#1f6feb")
        head.pack(fill="x", side="top")
        tk.Label(
            head,
            text="Temu 流量监测 · 本机版",
            bg="#1f6feb",
            fg="white",
            font=self.f_title,
        ).pack(anchor="w", padx=16, pady=(12, 0))
        tk.Label(
            head,
            text="仅流量待关注/下降/在售 · 上下架在服务器 · 绿=安全 · 红=常驻 · 蓝=工具",
            bg="#1f6feb",
            fg="#d7e6ff",
            font=self.f_sub,
        ).pack(anchor="w", padx=16, pady=(2, 12))

        self.status = tk.StringVar(value="就绪　·　" + BASE_DIR)
        tk.Label(
            root,
            textvariable=self.status,
            bg="#e9edf1",
            fg="#444",
            font=self.f_status,
            anchor="w",
        ).pack(fill="x", side="bottom", ipady=4)

        mid = tk.Frame(root, bg="#f4f6f8")
        mid.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(mid, bg="#f4f6f8", highlightthickness=0, bd=0)
        vsb = tk.Scrollbar(mid, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        body = tk.Frame(self._canvas, bg="#f4f6f8")
        self._body_win = self._canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", self._on_body_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        root.bind_all("<MouseWheel>", self._on_mousewheel)
        root.bind_all("<Button-4>", lambda e: self._canvas.yview_scroll(-3, "units"))
        root.bind_all("<Button-5>", lambda e: self._canvas.yview_scroll(3, "units"))

        pad = tk.Frame(body, bg="#f4f6f8")
        pad.pack(fill="both", expand=True, padx=14, pady=10)

        s0 = self._section(pad, "① 登录 / 流量监测")
        self._btn(
            s0,
            "登录 Temu",
            "safe",
            lambda: self.handle("login"),
            col=0,
            hint="仅监测档案·常驻时勿点",
        )
        self._btn(s0, "流量一轮 once", "safe", lambda: self.handle("once"), col=1, hint="待关注/下降/在售")
        self._btn(
            s0,
            "流量常驻 · 前台",
            "danger",
            lambda: self.handle("start"),
            full=True,
            hint="关窗口即停 · 需 YES",
        )
        self._btn(
            s0,
            "守护常驻 run-forever",
            "danger",
            lambda: self.handle("start_bg"),
            full=True,
            hint="崩溃自启 · 需 YES",
        )

        s1 = self._section(pad, "② 开机自启（计划任务 TemuMonitor）")
        self._btn(s1, "启用开机自启", "tool", lambda: self.handle("install_auto"), col=0, hint="UAC 提权")
        self._btn(s1, "取消开机自启", "neutral", lambda: self.handle("uninstall_auto"), col=1)

        s2 = self._section(pad, "③ 工具")
        self._btn(s2, "打开日志文件夹", "tool", lambda: self.handle("logs"), col=0)
        self._btn(s2, "打开项目目录", "tool", lambda: self.handle("folder"), col=1)
        self._btn(s2, "打开使用说明", "tool", lambda: self.handle("readme"), col=0)
        self._btn(s2, "npm install", "tool", lambda: self.handle("deps"), col=1)
        self._btn(s2, "检查 Node / 配置", "safe", lambda: self.handle("check"), full=True)

    def _on_body_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfigure(self._body_win, width=event.width)

    def _on_mousewheel(self, event):
        if event.delta:
            self._canvas.yview_scroll(int(-event.delta / 120), "units")

    def _section(self, parent, title):
        wrap = tk.Frame(parent, bg="#f4f6f8")
        wrap.pack(fill="x", pady=(4, 8))
        tk.Label(wrap, text=title, bg="#f4f6f8", fg="#333", font=self.f_sec, anchor="w").pack(
            fill="x", pady=(0, 4)
        )
        grid = tk.Frame(wrap, bg="#f4f6f8")
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=1, uniform="c")
        grid.columnconfigure(1, weight=1, uniform="c")
        grid._row = 0
        grid._col = 0
        return grid

    _COLORS = {
        "safe": ("#2e9e5b", "#268a4f"),
        "danger": ("#d64545", "#c23b3b"),
        "tool": ("#3b7dd8", "#356fc2"),
        "neutral": ("#6b7280", "#5c626b"),
    }

    def _btn(self, grid, text, kind, cmd, col=None, full=False, hint=None):
        bg, abg = self._COLORS[kind]
        label = text if not hint else f"{text}\n{hint}"
        b = tk.Button(
            grid,
            text=label,
            command=cmd,
            bg=bg,
            fg="white",
            activebackground=abg,
            activeforeground="white",
            font=self.f_btn,
            relief="flat",
            bd=0,
            cursor="hand2",
            justify="center",
            pady=8,
        )
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

    def handle(self, key):
        try:
            self._handle(key)
        except Exception as e:
            messagebox.showerror("启动失败", f"{key}\n\n{type(e).__name__}: {e}")
            self.status.set(f"失败：{key}")

    def _handle(self, key):
        if key == "logs":
            os.makedirs(LOG_DIR, exist_ok=True)
            os.makedirs(DATA_DIR, exist_ok=True)
            try:
                os.startfile(LOG_DIR)
            except Exception as e:
                messagebox.showerror("打开失败", str(e))
            self.status.set("已打开 logs")
            return
        if key == "folder":
            try:
                os.startfile(BASE_DIR)
            except Exception as e:
                messagebox.showerror("打开失败", str(e))
            self.status.set("已打开项目目录")
            return
        if key == "readme":
            for name in ("使用说明.txt", "PLUGIN_PARITY.md", "README.md"):
                p = os.path.join(BASE_DIR, name)
                if os.path.isfile(p):
                    try:
                        os.startfile(p)
                    except Exception as e:
                        messagebox.showerror("打开失败", str(e))
                    self.status.set("已打开 " + name)
                    return
            messagebox.showinfo("提示", "未找到使用说明文件")
            return
        if key == "check":
            lines = []
            n = shutil.which("node")
            lines.append("Node: " + (n or "NOT FOUND"))
            lines.append("Chrome userdata: " + ("OK" if os.path.isdir(os.path.join(BASE_DIR, ".userdata")) else "missing (run login)"))
            lines.append("config.json: " + ("OK" if os.path.isfile(os.path.join(BASE_DIR, "config.json")) else "missing — copy from config.example.json"))
            lines.append("node_modules: " + ("OK" if os.path.isdir(os.path.join(BASE_DIR, "node_modules")) else "run npm install"))
            lines.append("本机职责: 仅流量监测（上下架在服务器）")
            messagebox.showinfo("环境检查", "\n".join(lines))
            self.status.set("已检查环境")
            return

        if key not in TEMPLATES:
            messagebox.showerror("未知操作", key)
            return

        _, confirm_key = TEMPLATES[key]
        if confirm_key:
            msg = CONFIRM_MSG.get(confirm_key, "确认继续？")
            if not messagebox.askokcancel("确认", msg + "\n\n点「确定」继续。"):
                self.status.set("已取消")
                return

        if not shutil.which("node") and not detect_node():
            messagebox.showerror("缺少 Node.js", "请先安装 Node.js LTS：https://nodejs.org")
            return

        # 首次：缺依赖时在本窗口阻塞安装，装完再继续（避免另开窗装完还要再点一次、或点了登录却没 playwright）
        need_deps = key in ("once", "start", "start_bg", "login", "deps")
        nm = os.path.join(BASE_DIR, "node_modules")
        pw = os.path.join(nm, "playwright")
        if need_deps and key != "deps" and (not os.path.isdir(nm) or not os.path.isdir(pw)):
            messagebox.showinfo(
                "首次安装依赖",
                "未检测到 playwright 依赖。\n\n"
                "点「确定」后开始 npm install（约 1～3 分钟，\n"
                "窗口可能像卡住，请等状态栏提示完成）。\n"
                "装完会自动继续当前操作。",
            )
            self.status.set("正在 npm install，请稍候…")
            self.root.update_idletasks()
            try:
                r = subprocess.run(
                    "npm install",
                    cwd=BASE_DIR,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            except Exception as e:
                messagebox.showerror("npm install 失败", str(e))
                self.status.set("npm install 失败")
                return
            if r.returncode != 0 or not os.path.isdir(pw):
                err = (r.stderr or r.stdout or "")[-800:]
                messagebox.showerror(
                    "npm install 失败",
                    f"exit={r.returncode}\n\n{err}\n\n"
                    "也可在本目录手动打开 cmd 执行：npm install",
                )
                self.status.set("npm install 失败")
                return
            self.status.set("依赖已安装，继续…")
            self.root.update_idletasks()

        launch_console(build_inner(key))
        self.status.set("已启动：" + key)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
