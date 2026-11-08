# /// script
# requires-python = ">=3.9"
# dependencies = ["OpenCC>=1.1.9"]
# ///
"""用英文查遊戲官方 zh-TW 譯名：lookup.py 片語 [片語...]

先列出英文完全相同的 token（最多 4 個），再列出英文包含這個片語的（最多 3 個）。
遊戲資料夾自動尋找，或用環境變數 ROR2_GAME 指定。
"""
import os
import re
import sys

import _paths

PAIR = re.compile(r'"([^"\\]+)"\s*:\s*"((?:[^"\\]|\\.)*)"')


def load(lang_dir, lang):
    out = {}
    for f in os.listdir(os.path.join(lang_dir, lang)):
        if not f.endswith(".json") or f.startswith("mod_"):
            continue
        text = open(os.path.join(lang_dir, lang, f), encoding="utf-8-sig").read()
        for k, v in PAIR.findall(text):
            out[k] = v
    return out


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    lang_dir = _paths.game_dir() / "Risk of Rain 2_Data" / "StreamingAssets" / "Language"
    en, zh = load(lang_dir, "en"), load(lang_dir, "zh-TW")
    for q in sys.argv[1:]:
        exact = [k for k, v in en.items() if v == q]
        part = [k for k, v in en.items() if q.lower() in v.lower() and k not in exact][:3]
        print(f"== {q}")
        for k in exact[:4]:
            print(f"   = {k}: {zh.get(k)}")
        for k in part:
            print(f"   ~ {k}: {en[k][:80]} => {zh.get(k, '')[:80]}")


if __name__ == "__main__":
    main()
