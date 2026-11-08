"""列出 Tank 的 token 程式會走到的所有模組方法，以及它們呼叫的外部方法和用到的欄位。

用法：closure.py <TanksMod 的 IL 匯出>
模組更新後 interp.py 出現 NotImplementedError 時，用這個看新版多呼叫了哪些外部方法，
再到 interp.py 的「模組以外的呼叫」補上。
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ildiff  # noqa: E402

m = ildiff.load(sys.argv[1])
roots = [x for x in m if re.search(r'Tokens::AddTokens\(\)|Tokens::AddXtraTokens\(\)|TanksPlugin::CreateTankDLC\(\)', x)]
seen=set(); q=list(roots); ext=collections.Counter(); flds=collections.Counter(); ops=collections.Counter()
while q:
    x=q.pop()
    if x in seen: continue
    seen.add(x)
    for ins in m[x]:
        op, _, arg = ins.partition(' ')
        ops[op]+=1
        if op in ('call','callvirt','newobj','ldftn'):
            if arg in m and 'TanksMod' in arg.split('::')[0]:
                q.append(arg)
            else:
                ext[op+' '+arg]+=1
        elif op in ('ldsfld','ldfld','stsfld','stfld','ldsflda','ldflda'):
            flds[op+' '+arg]+=1
print('ROOTS', roots)
print('== methods'); [print(' ',x) for x in sorted(seen)]
print('== ext'); [print(' ',c,k) for k,c in sorted(ext.items())]
print('== fields'); [print(' ',c,k) for k,c in sorted(flds.items())]
print('== ops', dict(ops))
