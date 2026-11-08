"""把修補套用到 repo 的 mods/*.json：apply.py <patch.json> [--dry]

mods 檔是 json.dumps(indent=2) + CRLF；先確認重新輸出和原檔逐位元組相同才寫入，
不會因為換行或排版不同而改動整個檔案（Git Bash 的 sed -i 會把 CRLF 改成 LF，不要用）。

patch 格式：{mod: {
  "version": "新版本號",
  "order": [錄製順序的 token, ...]（新 token 插在順序上前一個已存在的 token 後面）,
  "strings": {token: {"en": ..., "zh-TW": ...}}（zh-TW 可省略表示保留舊譯文）,
  "literals": [[分組, 舊英文, 新英文, 譯文或 null], ...]（就地換鍵，譯文 null 表示保留）,
  "remove": [token, ...]
}}
mod 是 mods 檔名（不含 .json）。
"""
import json
import sys

import _paths


def dump(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").replace("\n", "\r\n").encode("utf-8")


def apply(mod, p):
    path = _paths.MODS / f"{mod}.json"
    raw = open(path, "rb").read()
    data = json.loads(raw.decode("utf-8"))
    if dump(data) != raw:
        raise SystemExit(f"{mod}：重新輸出和原檔不同，格式不符")
    if "version" in p:
        data["version"] = p["version"]
    strings = data["strings"]
    order = p.get("order", [])
    for token, entry in p.get("strings", {}).items():
        if token in strings:
            strings[token]["en"] = entry["en"]
            if "zh-TW" in entry:
                strings[token]["zh-TW"] = entry["zh-TW"]
            continue
        if "zh-TW" not in entry and entry["en"] != "":
            raise SystemExit(f"{mod}：新 token {token} 沒有譯文")
        prev = None
        if token in order:
            for t in reversed(order[: order.index(token)]):
                if t in strings:
                    prev = t
                    break
        items = list(strings.items())
        at = len(items) if prev is None else [k for k, _ in items].index(prev) + 1
        items.insert(at, (token, dict(entry)))
        strings.clear()
        strings.update(items)
    for token in p.get("remove", []):
        del strings[token]
    for group, old, new, zh in p.get("literals", []):
        g = data["literals"][group]
        if old not in g:
            raise SystemExit(f"{mod}：literals[{group}] 找不到 {old!r}")
        items = [(new if k == old else k, (g[k] if zh is None else zh) if k == old else v) for k, v in g.items()]
        g.clear()
        g.update(items)
    return path, dump(data)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    patch = json.load(open(sys.argv[1], encoding="utf-8"))
    for mod, p in patch.items():
        path, out = apply(mod, p)
        if "--dry" in sys.argv:
            print(mod, "檢查通過")
        else:
            open(path, "wb").write(out)
            print(mod, "已寫入")


if __name__ == "__main__":
    main()
