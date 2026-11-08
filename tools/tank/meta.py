# /// script
# requires-python = ">=3.9"
# dependencies = ["dnfile>=0.18"]
# ///
"""讀 TanksMod.dll 的中繼資料：內嵌資源、列舉定義、型別階層。

用法：meta.py <dll> <輸出資料夾>
寫出 <輸出資料夾>/meta.json（interp.py 要用），並把每個內嵌資源存成 <輸出資料夾>/res_<名稱>
（其中 res_TanksMod.tanksbundle1 是 bundle_dump.py 要讀的 AssetBundle，每個版本都可能不同）。
"""
import json
import os
import struct
import sys

import dnfile


def main(dll, outdir):
    pe = dnfile.dnPE(dll)
    t = pe.net.mdtables
    # nested class -> enclosing
    enclosing = {}
    if t.NestedClass:
        for r in t.NestedClass:
            enclosing[r.NestedClass.row_index] = r.EnclosingClass.row_index

    def tname(idx):
        r = t.TypeDef[idx - 1]
        n = str(r.TypeName)
        if idx in enclosing:
            return tname(enclosing[idx]) + "/" + n
        ns = str(r.TypeNamespace)
        return (ns + "." + n) if ns else n

    def refname(ci):
        if ci is None or ci.row is None:
            return None
        r = ci.row
        if hasattr(r, "Extends"):
            return tname(ci.row_index)
        if hasattr(r, "ResolutionScope"):
            ns = str(r.TypeNamespace)
            n = str(r.TypeName)
            return (ns + "." + n) if ns else n
        return "<" + str(tab) + ">"

    # constants by field row index
    consts = {}
    for r in t.Constant or []:
        if hasattr(r.Parent.row, "Signature") and not hasattr(r.Parent.row, "ParamList"):
            consts[r.Parent.row_index] = (r.Type, bytes(r.Value.value))

    types = {}
    enums = {}
    nrows = len(t.TypeDef)
    for i in range(1, nrows + 1):
        r = t.TypeDef[i - 1]
        name = tname(i)
        base = refname(r.Extends)
        fields = [f.row_index for f in r.FieldList] if r.FieldList else []
        types[name] = {"base": base, "fields": [str(t.Field[fi - 1].Name) for fi in fields]}
        if base == "System.Enum":
            vals = []
            for fi in fields:
                fr = t.Field[fi - 1]
                fname = str(fr.Name)
                if fname == "value__":
                    continue
                if fi in consts:
                    typ, raw = consts[fi]
                    size = len(raw)
                    fmt = {1: "<b", 2: "<h", 4: "<i", 8: "<q"}[size]
                    v = struct.unpack(fmt, raw)[0]
                else:
                    v = None
                vals.append([fname, v])
            enums[name] = vals

    res = []
    for rr in pe.net.resources:
        rname = str(rr.name)
        data = rr.data
        res.append({"name": rname, "size": len(data) if data else 0})
        if data:
            with open(os.path.join(outdir, "res_" + rname), "wb") as f:
                f.write(data)
    with open(os.path.join(outdir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"resources": res, "enums": enums, "types": types}, f, ensure_ascii=False, indent=1)
    print("resources:", res)
    print("enums:", len(enums), "types:", len(types))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
