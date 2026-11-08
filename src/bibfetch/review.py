"""Interactive HTML review of a bibliography change, from two rendered .bbl files.

One card per changed reference (as the PDF prints it), word-level red/green
highlights, an Accept checkbox + comment per entry (saved in the
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
def bib_entries(path: str | None) -> dict[str, str]:
    """Raw BibTeX source of each entry, by key (for the optional BibTeX panel)."""
    if not path:
        return {}
    t = open(path, encoding="utf-8").read()
    out = {}
    for m in re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,", t):
        depth, j = 0, t.index("{", m.start())
        while j < len(t):
            depth += {"{": 1, "}": -1}.get(t[j], 0)
            if depth == 0:
                break
            j += 1
        out[m.group(1)] = t[m.start():j + 1]
    return out


def write_review(before_bbl: str, after_bbl: str, out_html: str, title: str = "Bibliography review",
                 before_bib: str | None = None, after_bib: str | None = None) -> tuple[int, int]:
    """Write the review page; returns (changed, total) cited entries.
    With before_bib/after_bib, each card gets a collapsed BibTeX source diff."""
    before=items(before_bbl); after=dict(items(after_bbl))
    bib_a, bib_b = bib_entries(before_bib), bib_entries(after_bib)
    rows=[];n=0
    for k,a in before:
        b=after.get(k,"(missing)")
        if a==b: continue
        n+=1; da,db=wdiff(a,b); kk=html.escape(k)
        bibhtml=""
        if k in bib_a or k in bib_b:
            ra,rb=wdiff(bib_a.get(k,"(not in before .bib)"),bib_b.get(k,"(not in after .bib)"))
            bibhtml=f'<details><summary>BibTeX</summary><div class="bib"><div><span class="tag">before</span><pre>{ra}</pre></div><div><span class="tag">after</span><pre>{rb}</pre></div></div></details>' 
        rows.append(f'''<section data-key="{kk}"><div class="head"><h2>{n}. <code>{kk}</code></h2>
    <label class="choice"><input type="checkbox"> Accept</label></div>
    <div class="row old"><span class="tag">before</span><p>{da}</p></div><div class="row new"><span class="tag">after</span><p>{db}</p></div>{bibhtml}
    <textarea placeholder="Comment (optional)" rows="1"></textarea></section>''')
    page=f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{html.escape(title)}</title><style>
    :root{{--bg:#fff;--fg:#1c1c1c;--muted:#666;--card:#f6f6f4;--del:#ffd7d5;--delfg:#8a1c14;--ins:#cdf0d3;--insfg:#0f5a22;--line:#e3e3e0;--acc:#2a6;--rej:#c33;--chg:#c80}}
    @media (prefers-color-scheme:dark){{:root{{--bg:#161616;--fg:#e8e8e8;--muted:#9a9a9a;--card:#202020;--del:#5a1f1c;--delfg:#ffb4ad;--ins:#173d22;--insfg:#9be3ad;--line:#333}}}}
    body{{background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,system-ui,sans-serif;max-width:980px;margin:0 auto;padding:24px 16px 120px}}
    h1{{font-size:22px;margin:0 0 4px}} .sub{{color:var(--muted);margin:0 0 20px}}
    section{{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--line);border-radius:8px;padding:12px 16px;margin:0 0 14px}}
    section.ok{{border-left-color:var(--acc)}} section.note{{border-left-color:var(--chg)}}
    .head{{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}}
    h2{{font-size:14px;margin:0;color:var(--muted);font-weight:600}} code{{font-size:13px}}
    .choice{{display:flex;gap:14px;font-size:13px}} .choice label{{cursor:pointer}}
    .row{{display:flex;gap:10px;align-items:baseline}} .row p{{margin:4px 0}}
    .tag{{flex:0 0 52px;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}}
    del{{background:var(--del);color:var(--delfg);text-decoration:line-through;border-radius:3px;padding:0 2px}}
    ins{{background:var(--ins);color:var(--insfg);text-decoration:none;border-radius:3px;padding:0 2px}}
    details{{margin-top:6px;font-size:13px}} summary{{cursor:pointer;color:var(--muted)}}
    .bib{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:6px}} @media (max-width:700px){{.bib{{grid-template-columns:1fr}}}}
    pre{{margin:2px 0 0;white-space:pre-wrap;word-break:break-word;font-size:12px;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px}}
    textarea{{width:100%;box-sizing:border-box;margin-top:8px;font:inherit;font-size:14px;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);resize:vertical}}
    .bar{{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:10px;justify-content:center;align-items:center;flex-wrap:wrap}}
    button{{font:inherit;font-size:14px;padding:6px 12px;border-radius:6px;border:1px solid var(--line);background:var(--bg);color:var(--fg);cursor:pointer}}
    #status{{color:var(--muted);font-size:13px}}
    </style></head><body><h1>{html.escape(title)}</h1>
    <p class="sub">Rendered references as the PDF shows them. {n} of {len(before)} cited entries changed; unchanged entries hidden. <del>red</del> = removed, <ins>green</ins> = added. Choices and comments are saved in this browser; use <b>Copy feedback</b> to paste them back to Claude.</p>
    {''.join(rows)}
    <div class="bar"><span id="status"></span><button id="acceptRest">Accept all without comments</button><button id="copy">Copy feedback</button></div>
    <script>
    const KEY='bibreview:'+location.pathname; let st={{}};
    try{{st=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
    const secs=[...document.querySelectorAll('section')];
    function save(){{try{{localStorage.setItem(KEY,JSON.stringify(st))}}catch(e){{}} render()}}
    function render(){{let a=0,cm=0;secs.forEach(s=>{{const e=st[s.dataset.key]||{{}};const c=(e.comment||'').trim();s.className=e.ok?'ok':(c?'note':'');if(e.ok)a++;if(c)cm++}});
    document.getElementById('status').textContent=`${{a}} of ${{secs.length}} accepted · ${{cm}} with comments`}}
    secs.forEach(s=>{{const k=s.dataset.key,e=st[k]||{{}},ta=s.querySelector('textarea');
     const cb=s.querySelector('input[type=checkbox]');cb.checked=!!e.ok; ta.value=e.comment||'';
     cb.addEventListener('change',()=>{{st[k]={{...(st[k]||{{}}),ok:cb.checked}};save()}});
     ta.addEventListener('input',()=>{{st[k]={{...(st[k]||{{}}),comment:ta.value}};save()}});}});
    document.getElementById('acceptRest').onclick=()=>{{secs.forEach(s=>{{const k=s.dataset.key,e=st[k]||{{}};if(!(e.comment||'').trim()){{st[k]={{...e,ok:true}};s.querySelector('input[type=checkbox]').checked=true}}}});save()}};
    document.getElementById('copy').onclick=async()=>{{const lines=secs.map(s=>{{const k=s.dataset.key,e=st[k]||{{}};return `${{k}}: ${{e.ok?'ACCEPT':'NOT ACCEPTED'}}${{(e.comment||'').trim()?' — '+e.comment.trim():''}}`}});
     const t='Bib review feedback:\\n'+lines.join('\\n');try{{await navigator.clipboard.writeText(t);document.getElementById('status').textContent='Copied to clipboard'}}catch(e){{prompt('Copy this:',t)}}}};
    render();
    </script></body></html>"""
    with open(out_html, "w", encoding="utf-8") as fh:
        fh.write(page)
    return n, len(before)
