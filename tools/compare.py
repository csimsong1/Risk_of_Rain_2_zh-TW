"""比對錄到的英文和 mods/<mod>.json 的 en。

用法：compare.py <mod> <錄製結果.json> [<錄製結果.json> ...]

<mod> 是 mods 檔名，可以只寫一部分（例如 Zabuza）。錄製結果可以是：
- rec.ps1 的輸出：[[token, 英文], [token, 英文, 語言], ...]，三欄的只取語言是 en 的；
- tank/interp.py 這類的輸出：{token: 英文}。
同一個 token 錄到兩次時取第一次（R2API 的 LanguageAPI.Add 保留先註冊的）。

先錄舊版、確認和 mods 檔完全相同（相同數 = 錄到數，其他都是 0），再錄新版比對差異。
"""
import json
import sys

import _paths


def load(path):
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, dict):
        return list(data.items())
    return [(row[0], row[1]) for row in data if len(row) == 2 or (len(row) == 3 and row[2] == "en")]


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    path = _paths.mod_file(sys.argv[1])
    d = json.load(open(path, encoding="utf-8-sig"))["strings"]
    rec = {}
    for p in sys.argv[2:]:
        for token, text in load(p):
            rec.setdefault(token, text)
    same = [k for k in rec if k in d and d[k]["en"] == rec[k]]
    diff = [k for k in rec if k in d and d[k]["en"] != rec[k]]
    new = [k for k in rec if k not in d]
    gone = [k for k in d if k not in rec]
    print(f"{path.stem}：錄到 {len(rec)}，相同 {len(same)}，不同 {len(diff)}，新增 {len(new)}，檔案有但沒錄到 {len(gone)}")
    order_rec = [k for k in rec if k in d]
    order_file = [k for k in d if k in rec]
    if order_rec != order_file:
        print("  （兩邊共有的 token 順序不同；新 token 要插在錄製順序的前一個 token 後面）")
    for k in diff:
        print(f"  ~ {k}\n    舊: {d[k]['en']!r}\n    新: {rec[k]!r}")
    for k in new:
        print(f"  + {k}: {rec[k]!r}")
    for k in gone:
        print(f"  ? {k}: {d[k]['en'][:100]!r}")


if __name__ == "__main__":
    main()
