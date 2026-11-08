# /// script
# requires-python = ">=3.9"
# dependencies = ["UnityPy>=1.25.4,<2"]
# ///
"""從 Tank 內嵌的 AssetBundle 匯出 prefab 的 GameObject 階層。

用法：bundle_dump.py <bundle> <輸出.json> <根物件名稱> [<根物件名稱> ...]
interp.py 要的是：bundle_dump.py res_TanksMod.tanksbundle1 prefabs.json mdlBasicTank mdlBasicXtraTank
每個節點：{name, active, pid, components: [{pid, cls, data?}], children: [...]}
MonoBehaviour 元件帶有腳本類別（namespace.class）和完整的 typetree。
"""
import json
import sys

import UnityPy


def main(bundle, out, roots):
    env = UnityPy.load(bundle)
    objs = {}
    for o in env.objects:
        objs[o.path_id] = o
    scripts = {}

    def script_name(pptr):
        pid = pptr["m_PathID"]
        if pid in scripts:
            return scripts[pid]
        if pptr["m_FileID"] != 0 or pid not in objs:
            scripts[pid] = "<external %s:%s>" % (pptr["m_FileID"], pid)
            return scripts[pid]
        d = objs[pid].read_typetree()
        ns = d.get("m_Namespace", "")
        n = (ns + "." if ns else "") + d["m_ClassName"]
        scripts[pid] = n
        return n

    def comp(pid):
        o = objs[pid]
        t = o.type.name
        c = {"pid": pid, "cls": t}
        if t == "MonoBehaviour":
            try:
                d = o.read_typetree()
            except Exception as e:  # noqa
                c["error"] = repr(e)
                return c, None
            c["cls"] = script_name(d["m_Script"])
            c["data"] = {k: v for k, v in d.items() if k not in ("m_GameObject", "m_Script")}
            return c, None
        if t in ("Transform", "RectTransform"):
            d = o.read_typetree()
            return c, d
        return c, None

    def node(go_pid):
        g = objs[go_pid].read_typetree()
        n = {"name": g["m_Name"], "active": bool(g["m_IsActive"]), "pid": go_pid, "components": [], "children": []}
        tr = None
        for cp in g["m_Component"]:
            pp = cp["component"]
            if pp["m_FileID"] != 0 or pp["m_PathID"] not in objs:
                n["components"].append({"pid": pp["m_PathID"], "cls": "<missing>"})
                continue
            c, d = comp(pp["m_PathID"])
            n["components"].append(c)
            if d is not None:
                tr = d
        if tr is not None:
            for ch in tr["m_Children"]:
                t = objs[ch["m_PathID"]].read_typetree()
                n["children"].append(node(t["m_GameObject"]["m_PathID"]))
        return n

    result = {}
    for o in env.objects:
        if o.type.name != "GameObject":
            continue
        g = o.read_typetree()
        if g["m_Name"] not in roots:
            continue
        # root = transform without father
        is_root = False
        for cp in g["m_Component"]:
            pp = cp["component"]
            oo = objs.get(pp["m_PathID"])
            if oo is not None and oo.type.name in ("Transform", "RectTransform"):
                t = oo.read_typetree()
                is_root = t["m_Father"]["m_PathID"] == 0
        if not is_root:
            continue
        if g["m_Name"] in result:
            print("WARNING: duplicate root", g["m_Name"])
        result[g["m_Name"]] = node(o.path_id)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    for k, v in result.items():
        cnt = [0]

        def walk(n):
            cnt[0] += 1
            for c in n["children"]:
                walk(c)
        walk(v)
        print(k, "nodes:", cnt[0])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
