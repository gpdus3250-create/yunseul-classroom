#!/usr/bin/env python3
"""Temporary inspection of the public weekly guide's extractable layout."""
from pathlib import Path
import fitz, json
pdf=Path("weekly-data/2026-11-23/original.pdf")
doc=fitz.open(pdf)
res={"source":str(pdf),"page_count":len(doc),"pages":[]}
for i,page in enumerate(doc):
    text=page.get_text("text",sort=True)
    words=page.get_text("words",sort=True)
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    res["pages"].append({"page":i+1,"char_count":len(text),"lines":lines[:240],
        "keyword_lines":[{"i":j,"text":v} for j,v in enumerate(lines) if any(t in v for t in ("국어","수학","단원","덧셈","뺄셈","놀이","문장"))][:60]})
Path("weekly-data/lesson-debug.json").write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"pages":len(doc),"characters":sum(p["char_count"] for p in res["pages"]),"line_count":sum(len(p["lines"]) for p in res["pages"])},ensure_ascii=False))
