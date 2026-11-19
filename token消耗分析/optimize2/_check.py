import re, io, sys, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE = r'c:\Users\24221\Desktop\test-team-2\token消耗分析\optimize2'
txt=open(BASE+r'\session-ses_e136.md',encoding='utf-8').read()
lines=txt.split('\n')
print("=== write calls: filePath + content head ===")
w=re.findall(r'\*\*Tool:\s*write\*\*.*?\{(.*?)\}\s*```',txt,re.S)
blocks=re.findall(r'\*\*Tool:\s*write\*\*(.*?)(?=\*\*Tool:|\n---|\Z)',txt,re.S)
for i,b in enumerate(blocks):
    p=re.search(r'"filePath"\s*:\s*"([^"]*)"',b)
    c=re.search(r'"content"\s*:\s*"([^"]{0,120})',b)
    print(f"  W{i+1}: path={p.group(1).split('/')[-1] if p else '?':28s} content={c.group(1)[:70] if c else ''}")
print("\n=== all bash with full command ===")
bb=re.findall(r'\*\*Tool:\s*bash\*\*(.*?)(?=\*\*Tool:|\n---|\Z)',txt,re.S)
for i,b in enumerate(bb):
    c=re.search(r'"command"\s*:\s*"([^"]*)"',b)
    cmd=c.group(1) if c else '?'
    print(f"  B{i+1}: {cmd[:180]}")
print("\n=== grep '逐条' / 'one by one' context ===")
for m in re.finditer(r'逐条',txt):
    s=max(0,m.start()-80); e=min(len(txt),m.end()+80)
    print("  ",txt[s:e].replace('\n',' ')[:170])
