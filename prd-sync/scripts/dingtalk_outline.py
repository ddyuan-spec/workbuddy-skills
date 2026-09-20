import json,sys,re
p=sys.argv[1]
d=json.load(open(p,encoding='utf-8'))
def walk(n,out):
    if isinstance(n,list) and n:
        tag=n[0]
        if isinstance(tag,str) and re.match(r'^h[1-4]$',tag):
            # collect text
            txt=[]
            def w2(x):
                if isinstance(x,str): txt.append(x)
                elif isinstance(x,list):
                    for y in x: w2(y)
            for c in n[1:]: w2(c)
            out.append((tag,''.join(txt).strip()))
        for c in n[1:]: walk(c,out)
out=[]
walk(d,out)
for t,s in out: print(f"{t} | {s}")
