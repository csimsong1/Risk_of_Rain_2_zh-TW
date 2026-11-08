"""列出 IL 匯出裡呼叫了符合正規表示式的方法，以及呼叫次數：callers.py <il 檔> <regex>

找出所有註冊文字的地方用，例如 Zerneas 系列：
    callers.py work/il/Zerneas-ZabuzaMod@0.7.1@ZabuzaMod.dll.il "\\.Modules\\.Language::Add\\("
列出的方法（AddSpanish 這類其他語言的除外）就是 rec.ps1 -Call 要執行的。
"""
import re
import sys


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    pat = re.compile(sys.argv[2])
    cur, hits = None, {}
    for line in open(sys.argv[1], encoding="utf-8"):
        if line.startswith("## "):
            cur = line[3:].strip()
        elif line.startswith(("call ", "callvirt ", "newobj ")) and pat.search(line):
            hits[cur] = hits.get(cur, 0) + 1
    for m, n in hits.items():
        print(f"{n:4d}  {m}")


if __name__ == "__main__":
    main()
