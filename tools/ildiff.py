"""比對同一模組新舊版本的 IL 匯出（ildump.ps1 -Mod 的輸出），以及 r2modman 快取裡的非 DLL 文字檔。

用法：ildiff.py [模組名稱的一部分] [--il 資料夾]

列出新增和刪除的 ldstr 字串、方法的增減與改變、數字常數（ldc.*）改變的方法，以及改變的文字檔。
同一個模組匯出超過兩個版本時，只比最新的兩個。數字常數不會出現在字串差異裡，
所以只要有「數字改變」，就要重新錄製並用 compare.py 比對。
"""
from __future__ import annotations

import argparse
import collections
import filecmp
import os
import re

import _paths

TEXT_EXT = {".json", ".txt", ".language", ".lang", ".csv", ".yaml", ".yml", ".xml"}


def version_key(version):
    return [(0, int(x), "") if x.isdigit() else (1, 0, x) for x in re.split(r"[.\-]", version)]


def load(path):
    """IL 匯出 -> {方法全名: [指令, ...]}。"""
    methods, cur = {}, None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("## "):
            cur = line[3:]
            methods[cur] = []
        else:
            methods[cur].append(line)
    return methods


def strings(methods):
    c = collections.Counter()
    for body in methods.values():
        for ins in body:
            if ins.startswith("ldstr "):
                c[ins[6:]] += 1
    return c


def nums(body):
    return [ins for ins in body if ins.startswith(("ldc.r4", "ldc.r8", "ldc.i4"))]


def text_files(cache, mod, old, new):
    da, db = cache / mod / old, cache / mod / new
    for root, _, fs in os.walk(db):
        for f in fs:
            if os.path.splitext(f)[1].lower() not in TEXT_EXT or f == "manifest.json":
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, db)
            q = os.path.join(da, rel)
            if not os.path.exists(q):
                print(f"  檔案新增: {rel}")
            elif not filecmp.cmp(p, q, shallow=False):
                print(f"  檔案改變: {rel}")
    for root, _, fs in os.walk(da):
        for f in fs:
            rel = os.path.relpath(os.path.join(root, f), da)
            if os.path.splitext(f)[1].lower() in TEXT_EXT and not os.path.exists(db / rel):
                print(f"  檔案刪除: {rel}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("only", nargs="?", help="只比對名稱包含這段文字的模組")
    ap.add_argument("--il", default=str(_paths.WORK / "il"), help="IL 匯出的資料夾（預設 work/il）")
    args = ap.parse_args()

    files = collections.defaultdict(dict)
    for f in os.listdir(args.il):
        if f.count("@") != 2 or not f.endswith(".il"):
            continue
        mod, ver, dll = f[:-3].split("@")
        files[(mod, dll)][ver] = os.path.join(args.il, f)
    done = set()
    for (mod, dll), vers in sorted(files.items()):
        if args.only and args.only.lower() not in mod.lower():
            continue
        if len(vers) < 2:
            print(f"=== {mod} {dll}：只有 {', '.join(vers)}，新版或舊版沒有這個 DLL")
            continue
        old, new = sorted(vers, key=version_key)[-2:]
        a, b = load(vers[old]), load(vers[new])
        print(f"=== {mod} {dll} {old} -> {new}")
        sa, sb = strings(a), strings(b)
        changed = [m for m in a if m in b and a[m] != b[m]]
        print(f"  methods: +{len(set(b) - set(a))} -{len(set(a) - set(b))} changed {len(changed)}")
        for s in sorted(sb - sa):
            print("  + " + s)
        for s in sorted(sa - sb):
            print("  - " + s)
        for m in changed:
            if nums(a[m]) != nums(b[m]):
                print(f"  # 數字改變: {m}")
        if (mod, old, new) not in done:
            done.add((mod, old, new))
            text_files(_paths.CACHE, mod, old, new)


if __name__ == "__main__":
    main()
