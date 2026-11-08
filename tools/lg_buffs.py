"""對 LookingGlass 的 BuffDefinitions::SetupEnglishDefs 做堆疊求值，輸出 {token: 英文}。
用法：lg_buffs.py <il 檔> <輸出 json>"""
import json
import re
import sys

METHOD = "System.Void LookingGlass.BuffDescriptions.BuffDefinitions::SetupEnglishDefs()"


class Buff(str):
    """BuffDef 欄位：資源名稱是 bd + 欄位名稱。"""


def run(body):
    stack, local, out = [], {}, {}

    def setup(key, text):
        out["LG_TOKEN_" + key] = text

    for line in body:
        op, _, arg = line.partition(" ")
        if op == "ldstr":
            stack.append(json.loads(arg))
        elif op.startswith("stloc"):
            idx = op.split(".")[1] if "." in op and op != "stloc.s" else arg.replace("V_", "")
            local[idx] = stack.pop()
        elif op.startswith("ldloc"):
            idx = op.split(".")[1] if "." in op and op != "ldloc.s" else arg.replace("V_", "")
            stack.append(local.get(idx, "<lang>"))
        elif op == "ldsfld" and arg.startswith("RoR2.BuffDef "):
            stack.append(Buff("bd" + arg.rsplit("::", 1)[1]))
        elif op == "ldsfld":
            stack.append("<languagesByName>")
        elif op.startswith("ldc.i4"):
            v = arg if arg else op.split(".")[2]
            stack.append(int(v.replace("m1", "-1")))
        elif op == "newarr":
            stack.append([None] * stack.pop())
        elif op == "dup":
            stack.append(stack[-1])
        elif op == "stelem.ref":
            v, i, arr = stack.pop(), stack.pop(), stack.pop()
            arr[i] = v
        elif op == "callvirt" and "Dictionary" in arg and "get_Item" in arg:
            stack.pop(); stack.pop(); stack.append("<lang>")
        elif op == "callvirt" and arg.endswith("UnityEngine.Object::get_name()"):
            stack.append(str(stack.pop()))
        elif op == "call" and "System.String::Concat(System.String[])" in arg:
            stack.append("".join(stack.pop()))
        elif op == "call" and "System.String::Concat(" in arg:
            n = arg.split("(", 1)[1].count("System.String")
            parts = [stack.pop() for _ in range(n)][::-1]
            stack.append("".join(parts))
        elif op == "call" and arg.endswith("::RegisterBuff(RoR2.Language,RoR2.BuffDef,System.String,System.String)"):
            desc, name, buff, _ = stack.pop(), stack.pop(), stack.pop(), stack.pop()
            setup("NAME_" + buff, name)
            setup("DESCRIPTION_" + buff, desc)
        elif op == "call" and arg.endswith("::SetupToken(RoR2.Language,System.String,System.String)"):
            text, key, _ = stack.pop(), stack.pop(), stack.pop()
            setup(key, text)
        elif op in ("nop", "ret"):
            pass
        else:
            raise SystemExit(f"不支援的指令：{line}")
    if stack:
        raise SystemExit(f"堆疊沒清空：{stack[:3]}")
    return out


def main():
    body, cur = [], None
    for line in open(sys.argv[1], encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("## "):
            cur = line[3:]
        elif cur == METHOD:
            body.append(line)
    out = run(body)
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(out), "條")


if __name__ == "__main__":
    main()
