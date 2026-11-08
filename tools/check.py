# /// script
# requires-python = ">=3.9"
# dependencies = ["OpenCC>=1.1.9"]
# ///
"""檢查 patch.json（apply.py 的格式）裡的譯文：check.py <patch.json>

- 標籤與佔位符要和英文一致（ror2_s2t.markup_diff，和安裝時的檢查相同）；
- 用字：寫「炮」不寫「砲」、寫「汙」不寫「污」、不用「數據」；
- 不能有 ror2_s2t.TERMS 列的大陸用語；
- 中文和英文、數字之間不加空格。
"""
import json
import re
import sys

import _paths  # noqa: F401（把 repo 加進 sys.path）
import ror2_s2t

WORDS = ["砲", "污", "數據"]
SPACE = re.compile(r"[一-鿿][ ]+[A-Za-z0-9]|[A-Za-z0-9%][ ]+[一-鿿]")


def problems(en, zh):
    msgs = []
    d = ror2_s2t.markup_diff(en, zh)
    if d:
        msgs.append(f"標籤或佔位符不一致：{d}")
    for w in WORDS:
        if w in zh:
            msgs.append(f"用字：{w}")
    for t in ror2_s2t.TERMS:
        if t in zh:
            msgs.append(f"大陸用語：{t}")
    if SPACE.search(re.sub(r"<[^>]*>", "", zh)):
        msgs.append("中英文之間有空格")
    return msgs


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    patch = json.load(open(sys.argv[1], encoding="utf-8"))
    bad = 0
    for mod, p in patch.items():
        rows = [(f"{mod} {k}", e["en"], e["zh-TW"]) for k, e in p.get("strings", {}).items() if "zh-TW" in e]
        rows += [(f"{mod} literals {new[:30]}", new, zh) for _, _, new, zh in p.get("literals", []) if zh]
        for where, en, zh in rows:
            msgs = problems(en, zh)
            if msgs:
                bad += 1
                print(where, *msgs, sep="\n   ")
    print("有問題的條目：", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
