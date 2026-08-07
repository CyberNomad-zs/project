"""Remove unused PostgreSQL install B (C:\\PostgreSQL\\16 + C:\\qingquan-pgdata).

Keeps the running instance under C:\\Program Files\\PostgreSQL\\16.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time


TARGETS = [
    r"C:\PostgreSQL\16",
    r"C:\qingquan-pgdata",
    r"C:\PostgreSQL",  # only if empty / leftover parent
]

KEEP_PREFIX = r"C:\Program Files\PostgreSQL\16"


def rm_tree(path: str) -> bool:
    if not os.path.exists(path):
        print(f"skip missing: {path}")
        return True
    # never touch the keep tree
    keep = os.path.normcase(os.path.abspath(KEEP_PREFIX))
    cur = os.path.normcase(os.path.abspath(path))
    if cur == keep or cur.startswith(keep + os.sep):
        print(f"REFUSE to remove keep path: {path}")
        return False

    print(f"removing: {path}")
    for i in range(5):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            print(f"removed: {path}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"  attempt {i + 1} failed: {exc}")
            time.sleep(1.0)
    print(f"FAILED: {path}")
    return False


def main() -> int:
    # stop/delete leftover service for install B
    subprocess.run(["sc.exe", "stop", "postgresql-qq-16"], capture_output=True, text=True)
    r = subprocess.run(["sc.exe", "delete", "postgresql-qq-16"], capture_output=True, text=True)
    print("sc delete postgresql-qq-16:", (r.stdout or r.stderr or "").strip())

    ok = True
    for p in TARGETS:
        if p == r"C:\PostgreSQL" and os.path.isdir(p):
            # only remove parent if empty or only leftover
            try:
                left = os.listdir(p)
            except OSError as exc:
                print(f"list {p} failed: {exc}")
                ok = False
                continue
            if left:
                print(f"parent not empty, skip {p}: {left}")
                continue
        if not rm_tree(p):
            ok = False

    print("\n=== exists check ===")
    for p in [KEEP_PREFIX, r"C:\PostgreSQL\16", r"C:\qingquan-pgdata", r"C:\PostgreSQL"]:
        print(f"exists={os.path.exists(p)} {p}")

    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
