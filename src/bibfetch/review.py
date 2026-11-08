"""Interactive HTML review of a bibliography change, from two rendered .bbl files.

One card per changed reference (as the PDF prints it), word-level red/green
highlights, Accept / Reject / Change + comment per entry (saved in the
browser), and a "Copy feedback" button that exports `key: CHOICE — comment`.
"""

import difflib
import html
import re
import unicodedata
ACC={"'":"\u0301","`":"\u0300","\"":"\u0308","^":"\u0302","~":"\u0303","v":"\u030c","c":"\u0327"}
def clean(s):
    s=re.sub(r"\{\\(['`\"^~vc])\s*\{?(\w)\}?\}", lambda m:m.group(2)+ACC[m.group(1)], s)
    s=re.sub(r"\\(['`\"^~vc])\s*\{?(\w)\}?", lambda m:m.group(2)+ACC[m.group(1)], s)
    s=unicodedata.normalize("NFC",s)
    s=s.replace("\\newblock","").replace("``","“").replace("''","”").replace("---","—").replace("--","–").replace("~"," ")
    s=re.sub(r"\{\\em\s+([^{}]*)\}", r"«\1»", s)
    s=s.replace("\\&","&").replace("{","").replace("}","")
    return re.sub(r"\s+"," ",s).strip()
def items(p):
    t=open(p, encoding="utf-8").read(); parts=re.split(r"\\bibitem\{([^}]+)\}",t)[1:]
    return [(parts[i],clean(parts[i+1].split("\\end{thebibliography}")[0])) for i in range(0,len(parts),2)]
def esc(t): return html.escape(t).replace("«","<i>").replace("»","</i>")
def wdiff(a,b):
    ta,tb=re.findall(r"\S+|\s+",a),re.findall(r"\S+|\s+",b); oa,ob=[],[]
    for op,i1,i2,j1,j2 in difflib.SequenceMatcher(None,ta,tb,autojunk=False).get_opcodes():
        A,B="".join(ta[i1:i2]),"".join(tb[j1:j2])
        if op=="equal": oa.append(esc(A)); ob.append(esc(B))
        else:
            if A: oa.append(f'<del>{esc(A)}</del>')
            if B: ob.append(f'<ins>{esc(B)}</ins>')
    return "".join(oa),"".join(ob)
def write_review(before_bbl: str, after_bbl: str, out_html: str, title: str = "Bibliography review") -> tuple[int, int]:
    """Write the review page; returns (changed, total) cited entries."""
    before=items(before_bbl); after=dict(items(after_bbl))
    rows=[];n=0
    for k,a in before:
        b=after.get(k,"(missing)")
        if a==b: continue
        n+=1; da,db=wdiff(a,b); kk=html.escape(k)
        rows.append(f'''<section data-key="{kk}"><div class="head"><h2>{n}. <code>{kk}</code></h2>
    <div class="choice"><label><input type="radio" name="{kk}" value="ok"> Accept</label><label><input type="radio" name="{kk}" value="reject"> Reject</label><label><input type="radio" name="{kk}" value="edit"> Change…</label></div></div>
    <div class="row old"><span class="tag">before</span><p>{da}</p></div><div class="row new"><span class="tag">after</span><p>{db}</p></div>
    <textarea placeholder="Comment (optional)" rows="1"></textarea></section>''')
    page=f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{html.escape(title)}</title><style>
    :root{{--bg:#fff;--fg:#1c1c1c;--muted:#666;--card:#f6f6f4;--del:#ffd7d5;--delfg:#8a1c14;--ins:#cdf0d3;--insfg:#0f5a22;--line:#e3e3e0;--acc:#2a6;--rej:#c33;--chg:#c80}}
    @media (prefers-color-scheme:dark){{:root{{--bg:#161616;--fg:#e8e8e8;--muted:#9a9a9a;--card:#202020;--del:#5a1f1c;--delfg:#ffb4ad;--ins:#173d22;--insfg:#9be3ad;--line:#333}}}}
    body{{background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,system-ui,sans-serif;max-width:980px;margin:0 auto;padding:24px 16px 120px}}
    h1{{font-size:22px;margin:0 0 4px}} .sub{{color:var(--muted);margin:0 0 20px}}
    section{{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--line);border-radius:8px;padding:12px 16px;margin:0 0 14px}}
    section.ok{{border-left-color:var(--acc)}} section.reject{{border-left-color:var(--rej)}} section.edit{{border-left-color:var(--chg)}}
    .head{{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}}
    h2{{font-size:14px;margin:0;color:var(--muted);font-weight:600}} code{{font-size:13px}}
    .choice{{display:flex;gap:14px;font-size:13px}} .choice label{{cursor:pointer}}
    .row{{display:flex;gap:10px;align-items:baseline}} .row p{{margin:4px 0}}
    .tag{{flex:0 0 52px;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}}
    del{{background:var(--del);color:var(--delfg);text-decoration:line-through;border-radius:3px;padding:0 2px}}
    ins{{background:var(--ins);color:var(--insfg);text-decoration:none;border-radius:3px;padding:0 2px}}
    textarea{{width:100%;box-sizing:border-box;margin-top:8px;font:inherit;font-size:14px;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);resize:vertical}}
    .bar{{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:10px;justify-content:center;align-items:center;flex-wrap:wrap}}
    button{{font:inherit;font-size:14px;padding:6px 12px;border-radius:6px;border:1px solid var(--line);background:var(--bg);color:var(--fg);cursor:pointer}}
    #status{{color:var(--muted);font-size:13px}}
    </style></head><body><h1>{html.escape(title)}</h1>
    <p class="sub">Rendered references as the PDF shows them. {n} of {len(before)} cited entries changed; unchanged entries hidden. <del>red</del> = removed, <ins>green</ins> = added. Choices and comments are saved in this browser; use <b>Copy feedback</b> to paste them back to Claude.</p>
    {''.join(rows)}
    <div class="bar"><span id="status"></span><button id="acceptRest">Accept all unmarked</button><button id="copy">Copy feedback</button></div>
    <script>
    const KEY='bibreview:'+location.pathname; let st={{}};
    try{{st=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
    const secs=[...document.querySelectorAll('section')];
    function save(){{try{{localStorage.setItem(KEY,JSON.stringify(st))}}catch(e){{}} render()}}
    function render(){{let c={{ok:0,reject:0,edit:0}};secs.forEach(s=>{{const v=(st[s.dataset.key]||{{}}).choice;s.className=v||'';if(v)c[v]++}});
    document.getElementById('status').textContent=`${{c.ok}} accepted · ${{c.reject}} rejected · ${{c.edit}} change · ${{secs.length-c.ok-c.reject-c.edit}} unmarked`}}
    secs.forEach(s=>{{const k=s.dataset.key,e=st[k]||{{}},ta=s.querySelector('textarea');
     if(e.choice){{const r=s.querySelector(`input[value="${{e.choice}}"]`);if(r)r.checked=true}} ta.value=e.comment||'';
     s.querySelectorAll('input').forEach(r=>r.addEventListener('change',()=>{{st[k]={{...(st[k]||{{}}),choice:r.value}};save()}}));
     ta.addEventListener('input',()=>{{st[k]={{...(st[k]||{{}}),comment:ta.value}};save()}});}});
    document.getElementById('acceptRest').onclick=()=>{{secs.forEach(s=>{{const k=s.dataset.key;if(!(st[k]||{{}}).choice){{st[k]={{...(st[k]||{{}}),choice:'ok'}};s.querySelector('input[value=ok]').checked=true}}}});save()}};
    document.getElementById('copy').onclick=async()=>{{const lines=secs.map(s=>{{const k=s.dataset.key,e=st[k]||{{}};return `${{k}}: ${{(e.choice||'UNMARKED').toUpperCase()}}${{e.comment?' — '+e.comment.trim():''}}`}});
     const t='Bib review feedback:\\n'+lines.join('\\n');try{{await navigator.clipboard.writeText(t);document.getElementById('status').textContent='Copied to clipboard'}}catch(e){{prompt('Copy this:',t)}}}};
    render();
    </script></body></html>"""
    with open(out_html, "w", encoding="utf-8") as fh:
        fh.write(page)
    return n, len(before)
