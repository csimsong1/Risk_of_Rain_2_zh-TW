# /// script
# requires-python = ">=3.9"
# dependencies = ["dnfile>=0.18", "OpenCC>=1.1.9"]
# ///
"""Celestial War Tank 專用的小型 CIL 直譯器：照 IL 匯出執行模組註冊文字的程式，錄下英文。

用法：interp.py <IL 匯出> <資料資料夾（meta.json、prefabs.json）> <輸出.json> [--rebuild]

依序執行 StaticBasicModels.Init、StaticXtraModels.Init、StaticTextures.Init、
Tokens.AddTokens、Tokens.AddXtraTokens、StandaloneAncientScepter 的 Tokens.AddTokens、
TanksPlugin.CreateTankDLC，記下每一次 R2API.LanguageAPI.Add(token, text)。
--rebuild 另外模擬實際的 TanksPlugin.Awake 在 token 程式之前跑的 Rebuild.Init 對資料的改動
（主炮塔改名成「<車體> Turret」、沒有炮塔的車體標成 turretless）。
輸出是 {token: 英文}，同一個 token 只留第一次（R2API 的行為），可以直接給 compare.py。
UnityEngine.KeyCode 的列舉值從遊戲的 UnityEngine.CoreModule.dll 讀，遊戲資料夾自動尋找或用 ROR2_GAME。
"""
import json
import math
import os
import re
import struct
import sys
from decimal import Decimal, ROUND_HALF_UP

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _paths  # noqa: E402

# ---------------------------------------------------------------- 值


def f32(x):
    x = float(x)
    if math.isnan(x) or math.isinf(x):
        return x
    try:
        return struct.unpack("<f", struct.pack("<f", x))[0]
    except OverflowError:
        return math.copysign(math.inf, x)


class F(float):
    """float32 的值"""


def mkf(x):
    return F(f32(x))


def i32(x):
    x = int(x) & 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


class Arr(list):
    def __init__(self, typ, items):
        super().__init__(items)
        self.typ = typ


class Box:
    def __init__(self, typ, val):
        self.typ, self.val = typ, val

    def __repr__(self):
        return "Box(%s,%r)" % (self.typ, self.val)


class Ref:
    def __init__(self, get, set_):
        self.get, self.set = get, set_


class TypeHandle:
    def __init__(self, name):
        self.name = name


class Dummy:
    """沒有模擬內容的 Unity／RoR2 物件（Sprite、ExpansionDef、AssetBundle…）。"""

    def __init__(self, typ, name=""):
        self.typ, self.name, self.fields = typ, name, {}

    def __repr__(self):
        return "Dummy(%s,%s)" % (self.typ, self.name)


class ListObj:
    def __init__(self):
        self.items = []


class Enumerator:
    def __init__(self, items):
        self.items, self.i, self.cur = list(items), -1, None


class ConfigEntry:
    def __init__(self, v):
        self.value = v


class KeyboardShortcut:
    def __init__(self, key):
        self.main_key = key


class GO:
    def __init__(self, node, parent):
        self.name = node["name"]
        self.active = node["active"]
        self.pid = node["pid"]
        self.parent = parent
        self.comps = [Comp(c, self) for c in node["components"]]
        self.children = [GO(ch, self) for ch in node["children"]]

    def active_in_hierarchy(self):
        g = self
        while g is not None:
            if not g.active:
                return False
            g = g.parent
        return True

    def __repr__(self):
        return "GO(%s)" % self.name


class Comp:
    def __init__(self, c, go):
        self.cls = c["cls"]
        if self.cls in ("Transform", "RectTransform"):
            self.cls = "UnityEngine." + self.cls
        self.pid = c["pid"]
        self.data = c.get("data", {})
        self.over = {}
        self.go = go

    def __repr__(self):
        return "Comp(%s@%s)" % (self.cls.rsplit(".", 1)[-1], self.go.name)


# ---------------------------------------------------------------- .NET 的數字格式化


def fmt_g(x, prec=7):
    x = float(x)
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0:
        return "0"
    s = "%.*e" % (prec - 1, x)
    m, e = s.split("e")
    e = int(e)
    neg = m.startswith("-")
    m = m.lstrip("-")
    digits = m.replace(".", "").rstrip("0") or "0"
    if -5 < e < prec:
        if e >= 0:
            if len(digits) <= e + 1:
                r = digits + "0" * (e + 1 - len(digits))
            else:
                r = digits[: e + 1] + "." + digits[e + 1:]
        else:
            r = "0." + "0" * (-e - 1) + digits
    else:
        r = digits[0] + ("." + digits[1:] if len(digits) > 1 else "") + "E" + ("+" if e >= 0 else "-") + "%02d" % abs(e)
    return ("-" if neg else "") + r


def fmt_custom(x, fmt, sig=7):
    m = re.fullmatch(r"0(?:\.(0+))?", fmt)
    if not m:
        raise NotImplementedError("custom format %r" % fmt)
    nd = len(m.group(1) or "")
    x = float(x)
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    d = Decimal("%.*e" % (sig - 1, x)) if sig else Decimal(repr(x))
    q = d.quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP)
    s = format(q, "f")
    if q == 0 and s.startswith("-"):
        s = s[1:]
    return s


ENUMS = {}


def enum_name(typ, v):
    vals = ENUMS[typ]
    for n, val in vals:
        if val == v:
            return n
    return str(v)


def to_str(v, fmt=None, typ=None):
    if isinstance(v, Box):
        typ, v = v.typ, v.val
    if v is None:
        return ""
    if typ in ENUMS:
        assert not fmt
        return enum_name(typ, v)
    if typ == "System.Single" or isinstance(v, F):
        return fmt_custom(v, fmt) if fmt else fmt_g(v)
    if typ == "System.Double":
        return fmt_custom(v, fmt, 15) if fmt else fmt_g(v, 15)
    if typ == "System.Boolean":
        return "True" if v else "False"
    if typ in ("System.Int32", "System.Int64", "System.UInt32") or isinstance(v, int):
        return fmt_custom(v, fmt) if fmt else str(int(v))
    if isinstance(v, str):
        return v
    raise NotImplementedError("to_str %r %r" % (typ, v))


def net_format(fmt, args):
    out = []
    i = 0
    while i < len(fmt):
        c = fmt[i]
        if c == "{":
            if fmt[i + 1: i + 2] == "{":
                out.append("{")
                i += 2
                continue
            j = fmt.index("}", i)
            spec = fmt[i + 1: j]
            head, _, f = spec.partition(":")
            idx, _, align = head.partition(",")
            s = to_str(args[int(idx)], f or None)
            if align:
                a = int(align)
                s = s.rjust(a) if a > 0 else s.ljust(-a)
            out.append(s)
            i = j + 1
        elif c == "}":
            if fmt[i + 1: i + 2] == "}":
                out.append("}")
                i += 2
                continue
            raise ValueError("bad format " + fmt)
        else:
            out.append(c)
            i += 1
    return "".join(out)


# ---------------------------------------------------------------- 讀取 IL 匯出


def load_il(path):
    methods, cur = {}, None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("## "):
            cur = line[3:]
            methods[cur] = []
        else:
            op, _, arg = line.partition(" ")
            methods[cur].append((op, arg))
    return methods


def split_top(s):
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch in "<[(":
            depth += 1
        elif ch in ">])":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        parts.append(cur)
    return parts


def parse_sig(sig):
    """'RET Type::Name<G>(P1,P2)' -> (ret, 'Type::Name<G>', [params])"""
    # 回傳型別是宣告型別前面那個空白之前的全部內容
    sp = sig.index(" ")
    ret = sig[:sp]
    rest = sig[sp + 1:]
    k = rest.index("::")
    p = rest.index("(", k)
    name = rest[:p]
    params = split_top(rest[p + 1: rest.rindex(")")])
    return ret, name, params


# ---------------------------------------------------------------- 直譯器


class VM:
    def __init__(self, methods, types, comps_by_pid, rebuild=False):
        self.m = methods
        self.types = types
        self.pids = comps_by_pid
        self.statics = {}
        self.cctor_done = set()
        self.records = []
        self.skip_cctor = {"TanksMod.Modules.Assets", "TanksMod.Modules.Config", "TanksMod.TanksPlugin"}
        self.trace = []

    # ---- 型別
    def is_a(self, cls, want):
        c = cls
        while c:
            if c == want:
                return True
            c = self.types.get(c, {}).get("base")
        return False

    def ensure_cctor(self, typ):
        if typ in self.cctor_done:
            return
        self.cctor_done.add(typ)
        if typ in self.skip_cctor:
            return
        name = "System.Void %s::.cctor()" % typ
        if name in self.m:
            self.run(name, [])

    # ---- 欄位
    def resolve(self, v):
        if isinstance(v, dict) and "m_PathID" in v:
            if v["m_PathID"] == 0:
                return None
            o = self.pids.get(v["m_PathID"])
            return o if o is not None else Dummy("external", str(v["m_PathID"]))
        return v

    def conv_field(self, ftype, v):
        if ftype.endswith("[]"):
            return Arr(ftype[:-2], [self.conv_field(ftype[:-2], x) for x in v])
        if ftype == "System.Single":
            return mkf(v)
        if ftype == "System.Double":
            return float(v)
        if ftype in ("System.Int32", "System.Boolean", "System.Byte", "System.Int64") or ftype in ENUMS:
            return int(v)
        if ftype == "System.String":
            return v
        return self.resolve(v)

    def read_field(self, obj, sig):
        ftype, _, rest = sig.partition(" ")
        fname = rest.split("::")[1]
        if isinstance(obj, Comp):
            if fname in obj.over:
                return obj.over[fname]
            if fname not in obj.data:
                raise KeyError("field %s missing on %r" % (fname, obj))
            return self.conv_field(ftype, obj.data[fname])
        if isinstance(obj, Dummy):
            return obj.fields.get(fname)
        raise NotImplementedError("ldfld on %r (%s)" % (obj, sig))

    def write_field(self, obj, sig, v):
        fname = sig.partition(" ")[2].split("::")[1]
        if isinstance(obj, Comp):
            obj.over[fname] = v
        elif isinstance(obj, Dummy):
            obj.fields[fname] = v
        else:
            raise NotImplementedError("stfld on %r" % (obj,))

    def sfield_key(self, sig):
        rest = sig.partition(" ")[2]
        typ = rest.split("::")[0]
        self.ensure_cctor(typ)
        return rest

    # ---- Unity 物件
    @staticmethod
    def go_of(o):
        if isinstance(o, GO):
            return o
        if isinstance(o, Comp):
            return o.go
        raise NotImplementedError("go_of %r" % (o,))

    def comps_in_children(self, go, typ, include_inactive):
        out = []
        if not include_inactive and not go.active_in_hierarchy():
            return out

        def rec(g):
            if not include_inactive and not g.active:
                return
            for c in g.comps:
                if self.is_a(c.cls, typ):
                    out.append(c)
            for ch in g.children:
                rec(ch)
        rec(go)
        return out

    def get_component(self, go, typ):
        for c in go.comps:
            if self.is_a(c.cls, typ):
                return c
        return None

    # ---- 模組以外的呼叫
    def external(self, op, sig, args, constrained):
        ret, name, params = parse_sig(sig)
        a = args

        def this():
            t = a[0]
            return t.get() if isinstance(t, Ref) else t

        g = re.match(r"(.*)::(\w+|\.ctor|\.cctor|op_\w+)(?:<(.*)>)?$", name)
        typ, meth, garg = g.group(1), g.group(2), g.group(3)
        name = typ + "::" + meth
        if name == "System.Environment::get_NewLine":
            return "\r\n"
        if typ == "System.String":
            if meth == "Concat":
                if params == ["System.String[]"]:
                    return "".join(x or "" for x in a[0])
                assert all(p == "System.String" for p in params), sig
                return "".join(x or "" for x in a)
            if meth == "Format":
                if params[-1] == "System.Object[]":
                    return net_format(a[0], list(a[1]))
                return net_format(a[0], a[1:])
            if meth == "Replace":
                return this().replace(a[1], a[2] or "")
            if meth == "ToUpper":
                return this().upper()
            if meth == "Trim":
                return this().strip()
            if meth == "Contains":
                return int(a[1] in this())
            if meth == "IsNullOrEmpty":
                return int(not a[0])
            if meth == "op_Equality":
                return int(a[0] == a[1])
            if meth == "op_Inequality":
                return int(a[0] != a[1])
        if typ == "System.Single" and meth == "ToString":
            v = this()
            return fmt_custom(v, a[1]) if len(params) == 1 else fmt_g(v)
        if typ == "System.Int32" and meth == "ToString":
            v = this()
            return fmt_custom(v, a[1]) if len(params) == 1 else str(int(v))
        if typ == "System.Object" and meth == "ToString":
            v = this()
            if constrained:
                if constrained in ENUMS:
                    return enum_name(constrained, v)
                return to_str(v, None, constrained)
            return to_str(v)
        if typ == "System.IDisposable" and meth == "Dispose":
            return None
        if name == "System.Type::GetTypeFromHandle":
            return a[0]
        if name == "System.Enum::GetNames":
            vals = ENUMS[a[0].name]
            srt = sorted(vals, key=lambda nv: nv[1] & 0xFFFFFFFFFFFFFFFF)
            return Arr("System.String", [n for n, _ in srt])
        if name == "R2API.LanguageAPI::Add":
            assert params == ["System.String", "System.String"], sig
            self.records.append((a[0], a[1]))
            return None
        if typ == "UnityEngine.Object":
            if meth == "op_Equality":
                return int(a[0] is a[1])
            if meth == "op_Inequality":
                return int(a[0] is not a[1])
            if meth == "op_Implicit":
                return int(a[0] is not None)
            if meth == "get_name":
                o = a[0]
                if isinstance(o, (GO, Dummy)):
                    return o.name
                return o.go.name
        if name == "UnityEngine.Mathf::Abs":
            return mkf(abs(a[0]))
        if meth == "get_gameObject" and typ in ("UnityEngine.Component", "UnityEngine.GameObject"):
            return self.go_of(a[0])
        if meth == "get_transform" and typ in ("UnityEngine.Component", "UnityEngine.GameObject"):
            return self.get_component(self.go_of(a[0]), "UnityEngine.Transform")
        if meth == "GetComponent" and typ in ("UnityEngine.Component", "UnityEngine.GameObject"):
            return self.get_component(self.go_of(a[0]), garg)
        if meth == "GetComponentsInChildren" and typ in ("UnityEngine.Component", "UnityEngine.GameObject"):
            inc = bool(a[1]) if len(params) == 1 else False
            return Arr(garg, self.comps_in_children(self.go_of(a[0]), garg, inc))
        if name in ("UnityEngine.AssetBundle::LoadAsset", "RoR2.LegacyResourcesAPI::Load"):
            return Dummy(garg, a[-1])
        if name == "UnityEngine.ScriptableObject::CreateInstance":
            return Dummy(garg)
        if name == "R2API.ContentAddition::AddExpansionDef":
            return 1
        if typ.startswith("BepInEx.Configuration.ConfigEntry`1<") and meth == "get_Value":
            return a[0].value
        if name == "BepInEx.Configuration.KeyboardShortcut::get_MainKey":
            return this().main_key
        if typ.startswith("System.Collections.Generic.List`1<") and meth == "GetEnumerator":
            return Enumerator(a[0].items)
        if typ.startswith("System.Collections.Generic.List`1<") and meth == "Add":
            a[0].items.append(a[1])
            return None
        if typ.startswith("System.Collections.Generic.List`1/Enumerator<"):
            e = this()
            if meth == "MoveNext":
                e.i += 1
                if e.i < len(e.items):
                    e.cur = e.items[e.i]
                    return 1
                e.cur = None
                return 0
            if meth == "get_Current":
                return e.cur
            if meth == "Dispose":
                return None
        raise NotImplementedError("external call %s %s" % (op, sig))

    def newobj(self, sig, args):
        ret, name, params = parse_sig(sig)
        if name.startswith("System.Collections.Generic.List`1<") and name.endswith("::.ctor") and not params:
            return ListObj()
        raise NotImplementedError("newobj " + sig)

    def is_internal(self, sig):
        return sig in self.m

    def nargs_external(self, op, sig):
        ret, name, params = parse_sig(sig)
        n = len(params)
        static_names = (
            "System.String::Concat", "System.String::Format", "System.String::IsNullOrEmpty",
            "System.String::op_Equality", "System.String::op_Inequality", "System.Environment::get_NewLine",
            "System.Type::GetTypeFromHandle", "System.Enum::GetNames", "R2API.LanguageAPI::Add",
            "UnityEngine.Object::op_Equality", "UnityEngine.Object::op_Inequality", "UnityEngine.Object::op_Implicit",
            "UnityEngine.Mathf::Abs", "RoR2.LegacyResourcesAPI::Load", "UnityEngine.ScriptableObject::CreateInstance",
            "R2API.ContentAddition::AddExpansionDef",
        )
        base = re.sub(r"<[^()]*>$", "", name)
        if op == "callvirt" or base not in static_names:
            n += 1
        return n

    # ---- 主迴圈
    def run(self, mname, args):
        body = self.m[mname]
        cls = mname.partition(" ")[2].split("::")[0]
        self.ensure_cctor(cls)
        loc = {}
        st = []
        pc = 0
        constrained = None
        while True:
            op, arg = body[pc]
            pc += 1
            if op == "nop":
                continue
            if op == "constrained.":
                constrained = arg
                continue
            c, constrained = constrained, None
            if op == "ldstr":
                st.append(json.loads(arg))
            elif op == "ldnull":
                st.append(None)
            elif op.startswith("ldc.i4"):
                if op == "ldc.i4.m1":
                    st.append(-1)
                elif op in ("ldc.i4.s", "ldc.i4"):
                    st.append(int(arg))
                else:
                    st.append(int(op.split(".")[2]))
            elif op == "ldc.r4":
                st.append(mkf({"NaN": "nan", "Infinity": "inf", "-Infinity": "-inf"}.get(arg, arg)))
            elif op == "ldc.r8":
                st.append(float(arg))
            elif op.startswith("ldloc"):
                if op.startswith("ldloca"):
                    k = int(arg.split("_")[1])
                    st.append(Ref((lambda k=k: loc.get(k)), (lambda v, k=k: loc.__setitem__(k, v))))
                else:
                    k = int(arg.split("_")[1]) if op.endswith(".s") or op == "ldloc" else int(op.split(".")[1])
                    st.append(loc.get(k))
            elif op.startswith("stloc"):
                k = int(arg.split("_")[1]) if op.endswith(".s") or op == "stloc" else int(op.split(".")[1])
                loc[k] = st.pop()
            elif op.startswith("ldarg"):
                if op.startswith("ldarga"):
                    raise NotImplementedError(op)
                k = int(op.split(".")[1])
                st.append(args[k])
            elif op == "dup":
                st.append(st[-1])
            elif op == "pop":
                st.pop()
            elif op in ("br", "br.s", "leave", "leave.s"):
                pc = int(arg[1:])
            elif op == "endfinally":
                raise NotImplementedError("endfinally reached by fallthrough in " + mname)
            elif op in ("brtrue", "brtrue.s", "brfalse", "brfalse.s"):
                v = st.pop()
                t = v is not None and v != 0 and v is not False
                if isinstance(v, (str, list, object)) and not isinstance(v, (int, float)):
                    t = v is not None
                if t == op.startswith("brtrue"):
                    pc = int(arg[1:])
            elif op.split(".")[0] in ("beq", "bne", "blt", "ble", "bgt", "bge"):
                b, a_ = st.pop(), st.pop()
                kind = op.split(".")[0]
                un = ".un" in op
                if isinstance(a_, float) or isinstance(b, float):
                    unordered = math.isnan(a_) or math.isnan(b)
                else:
                    unordered = False
                if kind == "beq":
                    r = a_ == b
                elif kind == "bne":
                    r = a_ != b
                elif unordered:
                    r = un
                else:
                    r = {"blt": a_ < b, "ble": a_ <= b, "bgt": a_ > b, "bge": a_ >= b}[kind]
                if r:
                    pc = int(arg[1:])
            elif op == "switch":
                v = st.pop()
                targets = [int(x[1:]) for x in arg.split(",")]
                if 0 <= v < len(targets):
                    pc = targets[v]
            elif op in ("ceq", "cgt", "cgt.un", "clt", "clt.un"):
                b, a_ = st.pop(), st.pop()
                if isinstance(a_, float) or isinstance(b, float):
                    unordered = math.isnan(a_) or math.isnan(b)
                else:
                    unordered = False
                    if op.endswith(".un") and isinstance(a_, int) and isinstance(b, int):
                        a_ &= 0xFFFFFFFF
                        b &= 0xFFFFFFFF
                if op == "ceq":
                    if a_ is None or b is None or not isinstance(a_, (int, float)):
                        r = a_ is b
                    else:
                        r = a_ == b
                elif unordered:
                    r = op.endswith(".un")
                elif op.startswith("cgt"):
                    if a_ is None or b is None:  # cgt.un obj, null  == (obj != null)
                        r = a_ is not None and b is None
                    else:
                        r = a_ > b
                else:
                    r = a_ < b
                st.append(int(r))
            elif op in ("add", "sub", "mul", "div", "rem"):
                b, a_ = st.pop(), st.pop()
                if isinstance(a_, F) or isinstance(b, F):
                    x, y = float(a_), float(b)
                    if op == "add":
                        r = x + y
                    elif op == "sub":
                        r = x - y
                    elif op == "mul":
                        r = x * y
                    elif op == "div":
                        if y == 0:
                            r = math.nan if x == 0 or math.isnan(x) else math.copysign(math.inf, x) * math.copysign(1, y)
                        else:
                            r = x / y
                    else:
                        r = math.fmod(x, y)
                    st.append(mkf(r))
                else:
                    if op == "add":
                        r = a_ + b
                    elif op == "sub":
                        r = a_ - b
                    elif op == "mul":
                        r = a_ * b
                    elif op == "div":
                        r = int(a_ / b)
                    else:
                        r = int(math.fmod(a_, b))
                    st.append(i32(r))
            elif op == "neg":
                v = st.pop()
                st.append(mkf(-v) if isinstance(v, F) else i32(-v))
            elif op == "conv.r4":
                st.append(mkf(st.pop()))
            elif op == "conv.r8":
                st.append(float(st.pop()))
            elif op == "conv.i4":
                v = st.pop()
                st.append(i32(math.trunc(v)) if isinstance(v, float) else i32(v))
            elif op == "ldlen":
                st.append(len(st.pop()))
            elif op == "newarr":
                n = st.pop()
                st.append(Arr(arg, [None] * n))
            elif op.startswith("stelem"):
                v, i, arr = st.pop(), st.pop(), st.pop()
                arr[i] = v
            elif op.startswith("ldelem"):
                i, arr = st.pop(), st.pop()
                st.append(arr[i])
            elif op == "ldfld":
                st.append(self.read_field(st.pop(), arg))
            elif op == "ldflda":
                o = st.pop()
                st.append(Ref((lambda o=o, s=arg: self.read_field(o, s)), (lambda v, o=o, s=arg: self.write_field(o, s, v))))
            elif op == "stfld":
                v, o = st.pop(), st.pop()
                self.write_field(o, arg, v)
            elif op == "ldsfld":
                k = self.sfield_key(arg)
                if k not in self.statics:
                    raise KeyError("static field not set: " + k)
                st.append(self.statics[k])
            elif op == "stsfld":
                self.statics[self.sfield_key(arg)] = st.pop()
            elif op == "box":
                st.append(Box(arg, st.pop()))
            elif op == "ldtoken":
                st.append(TypeHandle(arg))
            elif op in ("call", "callvirt"):
                if self.is_internal(arg):
                    ret, name, params = parse_sig(arg)
                    n = len(params) + (1 if op == "callvirt" else 0)
                    cargs = st[len(st) - n:] if n else []
                    del st[len(st) - n:]
                    r = self.run(arg, cargs)
                else:
                    n = self.nargs_external(op, arg)
                    cargs = st[len(st) - n:] if n else []
                    del st[len(st) - n:]
                    r = self.external(op, arg, cargs, c)
                if not arg.startswith("System.Void "):
                    st.append(r)
            elif op == "newobj":
                ret, name, params = parse_sig(arg)
                n = len(params)
                cargs = st[len(st) - n:] if n else []
                del st[len(st) - n:]
                st.append(self.newobj(arg, cargs))
            elif op == "ret":
                return st.pop() if st else None
            else:
                raise NotImplementedError("opcode %s in %s" % (op, mname))


# ---------------------------------------------------------------- 準備與執行


def load_keycode():
    import dnfile
    p = str(_paths.game_dir() / "Risk of Rain 2_Data" / "Managed" / "UnityEngine.CoreModule.dll")
    pe = dnfile.dnPE(p)
    t = pe.net.mdtables
    consts = {}
    for r in t.Constant:
        consts[r.Parent.row_index] = bytes(r.Value.value)
    for r in t.TypeDef:
        if str(r.TypeName) == "KeyCode" and str(r.TypeNamespace) == "UnityEngine":
            vals = []
            for f in r.FieldList:
                fr = t.Field[f.row_index - 1]
                if str(fr.Name) == "value__":
                    continue
                raw = consts[f.row_index]
                vals.append([str(fr.Name), struct.unpack("<i", raw)[0]])
            return vals
    raise KeyError("KeyCode")


def emulate_rebuild(vm, root):
    """TanksMod.Modules.Rebuild::Modify 對一個模型 prefab 的資料改動。"""
    ch = vm.get_component(root, "TanksMod.Modules.Components.BasicTank.ComponentsHandler")
    if ch is not None:
        ch.over["turrets"] = Arr("TanksMod.Modules.Components.User.Turret",
                                 vm.comps_in_children(root, "TanksMod.Modules.Components.User.Turret", True))
    log = []
    for h in vm.comps_in_children(root, "TanksMod.Modules.Components.User.TankModel", True):
        nm = vm.read_field(h, "System.String TanksMod.Modules.Components.User.TankModel::name")
        if not nm:
            h.over["name"] = nm = h.go.name
            log.append("hull name <- GO name %s" % nm)
        if not vm.read_field(h, "System.Boolean TanksMod.Modules.Components.User.TankModel::tankDestroyer"):
            mt = vm.read_field(h, "TanksMod.Modules.Components.User.Turret TanksMod.Modules.Components.User.TankModel::mainTurret")
            if mt is None:
                h.over["hasNoTurretOrPlacementReference"] = 1
                h.over["turretless"] = 1
                log.append("%s: no mainTurret -> hasNoTurretOrPlacementReference=turretless=true (dummy turret type None)" % nm)
            else:
                old = vm.read_field(mt, "System.String TanksMod.Modules.Components.User.Turret::name")
                mt.over["name"] = nm + " Turret"
                log.append("%s: mainTurret name %r -> %r" % (nm, old, nm + " Turret"))
    return log


def main():
    il, data, out = sys.argv[1:4]
    rebuild = "--rebuild" in sys.argv
    methods = load_il(il)
    meta = json.load(open(os.path.join(data, "meta.json"), encoding="utf-8"))
    ENUMS.update(meta["enums"])
    ENUMS["UnityEngine.KeyCode"] = load_keycode()
    prefabs = json.load(open(os.path.join(data, "prefabs.json"), encoding="utf-8"))
    roots = {k: GO(v, None) for k, v in prefabs.items()}
    pids = {}

    def idx(g):
        pids[g.pid] = g
        for c in g.comps:
            pids[c.pid] = c
        for ch in g.children:
            idx(ch)
    for r in roots.values():
        idx(r)
    vm = VM(methods, meta["types"], pids)
    S = vm.statics
    S["TanksMod.Modules.Assets::tankModel"] = roots["mdlBasicTank"]
    S["TanksMod.Modules.Assets::tankXtraModel"] = roots["mdlBasicXtraTank"]
    S["TanksMod.Modules.Assets::mainAssetBundle"] = Dummy("UnityEngine.AssetBundle", "tanksbundle1")
    S["TanksMod.Modules.Config::showExtraSkillInfo"] = ConfigEntry(1)
    S["TanksMod.Modules.Config::hoverMode_DescendKey"] = ConfigEntry(KeyboardShortcut(308))
    for c in ("TanksMod.Modules.Assets", "TanksMod.Modules.Config", "TanksMod.TanksPlugin"):
        vm.cctor_done.add(c)
    if rebuild:
        for k in ("mdlBasicTank", "mdlBasicXtraTank"):
            for line in emulate_rebuild(vm, roots[k]):
                print("[rebuild]", k, line)
    for m in ("System.Void TanksMod.Modules.Components.StaticBasicModels::Init()",
              "System.Void TanksMod.Modules.Components.StaticXtraModels::Init()",
              "System.Void TanksMod.Modules.Components.StaticTextures::Init()"):
        vm.run(m, [])
    print("basic hulls:", [vm.read_field(h, "System.String TanksMod.Modules.Components.User.TankModel::name") for h in S["TanksMod.Modules.Components.StaticBasicModels::hulls"]])
    print("basic turrets:", [(t.go.name, vm.read_field(t, "System.String TanksMod.Modules.Components.User.Turret::name")) for t in S["TanksMod.Modules.Components.StaticBasicModels::turrets"].items])
    print("xtra hulls:", [vm.read_field(h, "System.String TanksMod.Modules.Components.User.TankModel::name") for h in S["TanksMod.Modules.Components.StaticXtraModels::hulls"]])
    print("xtra turrets:", [(t.go.name, vm.read_field(t, "System.String TanksMod.Modules.Components.User.Turret::name")) for t in S["TanksMod.Modules.Components.StaticXtraModels::turrets"].items])
    sections = []
    for m in ("System.Void TanksMod.Modules.Tokens::AddTokens()",
              "System.Void TanksMod.Modules.Tokens::AddXtraTokens()",
              "System.Void TanksMod._DEPENDENCIES.StandaloneAncientScepter.Modules.Tokens::AddTokens()",
              "System.Void TanksMod.TanksPlugin::CreateTankDLC()"):
        n0 = len(vm.records)
        vm.run(m, [])
        sections.append((m, len(vm.records) - n0))
    for m, n in sections:
        print("%4d  %s" % (n, m))
    result = {}
    dups = []
    for k, v in vm.records:
        if k in result:  # R2API LanguageAPI.Add keeps the first value (ContainsKey -> skip)
            dups.append((k, result[k], v))
            continue
        result[k] = v
    for k, a_, b in dups:
        print("DUPLICATE KEY %r: first %r, then %r (R2API keeps first)" % (k, a_[:60], b[:60]))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print("records:", len(vm.records), "unique:", len(result))


if __name__ == "__main__":
    main()
