using System;
using System.Text;
using System.Diagnostics;
using System.Runtime.InteropServices;

public class ZiniaoWinMax {
  public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
  const int SW_RESTORE = 9;
  const int SW_MAXIMIZE = 3;

  static string ProcName(IntPtr hWnd) {
    try {
      uint pid;
      GetWindowThreadProcessId(hWnd, out pid);
      if (pid == 0) return "";
      var p = Process.GetProcessById((int)pid);
      return p != null ? (p.ProcessName ?? "") : "";
    } catch { return ""; }
  }

  public static int MaximizeMatching() {
    int n = 0;
    EnumWindows((hWnd, l) => {
      if (!IsWindowVisible(hWnd)) return true;
      var title = new StringBuilder(512);
      var cls = new StringBuilder(256);
      GetWindowText(hWnd, title, title.Capacity);
      GetClassName(hWnd, cls, cls.Capacity);
      string t = title.ToString();
      string c = cls.ToString();
      string pn = ProcName(hWnd);

      if (t.IndexOf("DevTools", StringComparison.OrdinalIgnoreCase) >= 0) return true;

      bool chromeClass = c.IndexOf("Chrome_WidgetWin", StringComparison.OrdinalIgnoreCase) >= 0;
      bool ziniaoNamed =
           pn.IndexOf("ziniao", StringComparison.OrdinalIgnoreCase) >= 0
        || pn.IndexOf("紫鸟", StringComparison.OrdinalIgnoreCase) >= 0
        || pn.IndexOf("SuperBrowser", StringComparison.OrdinalIgnoreCase) >= 0
        || pn.IndexOf("bitbrowser", StringComparison.OrdinalIgnoreCase) >= 0
        || pn.IndexOf("ziniaobrowser", StringComparison.OrdinalIgnoreCase) >= 0;

      bool titleHint =
           t.IndexOf("TikTok", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("tiktok", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("seller", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("Shop", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("紫鸟", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("Ziniao", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("ads-creation", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("商家中心", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("Seller Center", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("compass", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("Tiktok_Shop", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("Gardena", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("Deal to deal", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("Nookora", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("KK Seagull", StringComparison.OrdinalIgnoreCase) >= 0;

      // Skip plain Google Chrome home/new-tab windows
      bool plainGoogleChrome =
           pn.Equals("chrome", StringComparison.OrdinalIgnoreCase)
        && !titleHint
        && (t.IndexOf(" - Google Chrome", StringComparison.OrdinalIgnoreCase) >= 0
            || t.IndexOf("新标签页", StringComparison.OrdinalIgnoreCase) >= 0
            || t.IndexOf("New Tab", StringComparison.OrdinalIgnoreCase) >= 0
            || t.Length == 0);

      if (plainGoogleChrome) return true;

      // Match strategy (strict -> loose):
      //  1) strong title hint (any process)
      //  2) Ziniao-named process + Chromium class + non-empty title
      bool hit = false;
      if (titleHint) hit = true;
      else if (ziniaoNamed && chromeClass && t.Length >= 1) hit = true;

      if (hit) {
        if (IsIconic(hWnd)) ShowWindow(hWnd, SW_RESTORE);
        ShowWindow(hWnd, SW_MAXIMIZE);
        try { SetForegroundWindow(hWnd); } catch { }
        n++;
      }
      return true;
    }, IntPtr.Zero);
    return n;
  }
}
