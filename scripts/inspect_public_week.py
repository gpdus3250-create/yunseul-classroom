#!/usr/bin/env python3
from pathlib import Path
import json, fitz
doc=fitz.open("weekly-data/2026-11-23/original.pdf")
page=doc[0]
lines=[]
for block in page.get_text("dict")["blocks"]:
    if "lines" not in block: continue
    for ln in block["lines"]:
        spans=ln.get("spans",[])
        s="".join(x.get("text","") for x in spans).strip()
        if not s:continue
        rect=ln["bbox"]
        if any(term in s for term in ("상상","이야기","국 어","수 학","놀이터","질문","주제","안전","지금","기차","노래","선 따라","규칙","덧셈","낱말","문장","글의 의미")):
            lines.append(dict(text=s[:140],x=round(rect[0],1),y=round(rect[1],1),x2=round(rect[2],1)))
result={"page_w":page.rect.width,"page_h":page.rect.height,"lines":lines}
Path("weekly-data/source-inspection.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
print("Extracted",len(lines),"evidence fragments from the original weekly PDF")
