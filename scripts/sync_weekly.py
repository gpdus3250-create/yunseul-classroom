#!/usr/bin/env python3
"""Sync publicly readable grade-1 weekly notices; never fabricate a notice."""
import datetime as dt
import json
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse
import requests
from bs4 import BeautifulSoup

ROOT = "https://yunseul.icees.kr"
BOARD = "317890"
MENU = "020901"
LIST_URL = ROOT + "/boardCnts/list.do?" + urlencode({"boardID": BOARD, "m": MENU, "s": "yunseul"})

def allowed(url):
    p = urlparse(url)
    return p.scheme == "https" and p.hostname == "yunseul.icees.kr" and p.path.startswith("/boardCnts/")

def week_of(title, year):
    match_year = re.search(r"(20\d\d)\s*(?:학년도|[.\-/년])", title)
    if match_year:
        year = int(match_year.group(1))
    for pat in (r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", r"(?<!\d)(\d{1,2})\s*[./-]\s*(\d{1,2})(?!\d)"):
        match = re.search(pat, title)
        if not match:
            continue
        try:
            date = dt.date(year, int(match.group(1)), int(match.group(2)))
            return (date - dt.timedelta(days=date.weekday())).isoformat()
        except ValueError:
            pass
    return None

def posts_from(html, year):
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for row in soup.select("tr"):
        for a in row.select("a"):
            title = a.get_text(" ", strip=True)
            if not title or not (re.search(r"1\s*학년", title) or "주간학습" in title):
                continue
            if re.search(r"(?<!\d)[2-6]\s*학년", title):
                continue
            week = week_of(title, year)
            if not week:
                continue
            # School links often call fnView(boardID, boardSeq). The first
            # argument is the 6-digit board ID, not the 8-digit post ID.
            # Never confuse the board ID with a post ID.
            raw = " ".join([str(a.get("href", "")), str(a.get("onclick", "")),
                            str(a.get("data-url", "")), str(row.get("onclick", ""))])
            match = re.search(r"(?:boardSeq|board_seq)\s*(?:=|:)\s*['\"]?(\d{7,15})", raw, re.I)
            candidates = [x for x in re.findall(r"(?<!\d)\d{7,12}(?!\d)", raw)
                          if x != BOARD and not (x.startswith("20") and len(x) == 8)]
            seq = match.group(1) if match else (candidates[0] if candidates else None)
            if seq:
                url = ROOT + "/boardCnts/updateCnt.do?" + urlencode({"action":"view", "boardID":BOARD, "boardSeq":seq, "lev":"0", "m":MENU, "viewBoardID":BOARD})
            else:
                href = a.get("href", "")
                url = urljoin(ROOT, href) if href and not href.startswith(("javascript:", "#")) else ""
            if allowed(url) and not any(x["week"] == week and x["source_url"] == url for x in found):
                found.append({"week":week, "title":title, "source_url":url})
    return sorted(found, key=lambda x:x["week"], reverse=True)

def attachments_from(html):
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for a in soup.select("a"):
        raw = " ".join([a.get("href",""), a.get("onclick",""), a.get("data-url","")])
        match = re.search(r"fileSeq\s*[=:]\s*['\"]?([a-zA-Z0-9_-]{10,100})", raw, re.I)
        if not match:
            match = re.search(r"(?:fileDown|downloadFile|fnDownFile)\s*\(\s*['\"]([a-zA-Z0-9_-]{10,100})", raw, re.I)
        if match:
            seq = match.group(1)
            url = ROOT + "/boardCnts/fileDown.do?fileSeq=" + seq
            if url not in [f["url"] for f in found]:
                found.append({"url":url, "name":a.get_text(" ",strip=True)})
    return found

def suffix_of(response, name):
    hint = response.headers.get("content-disposition","") + " " + name + " " + response.url
    for ext in (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".hwpx", ".hwp"):
        if re.search(re.escape(ext) + r"(?!\w)", hint, re.I):
            return ext
    ctype = response.headers.get("content-type","").split(";")[0].lower()
    return {"application/pdf":".pdf", "image/png":".png", "image/jpeg":".jpg", "image/webp":".webp"}.get(ctype, "")

def verify_magic(path, suffix):
    with open(path,"rb") as f:
        head = f.read(16)
    if suffix == ".pdf": return head.startswith(b"%PDF")
    if suffix == ".png": return head.startswith(b"\x89PNG")
    if suffix in (".jpg",".jpeg"): return head.startswith(b"\xff\xd8")
    if suffix == ".webp": return head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    if suffix in (".hwp",".hwpx"): return head.startswith((b"PK\x03\x04",b"\xd0\xcf\x11\xe0"))
    return False

def convert_document(original, target):
    if not shutil.which("soffice"):
        return False
    with tempfile.TemporaryDirectory() as directory:
        cmd = ["soffice","-env:UserInstallation=file://"+directory+"/profile","--headless","--convert-to","pdf","--outdir",directory,str(original)]
        try:
            run = subprocess.run(cmd, timeout=60, capture_output=True)
            pdf = Path(directory, original.stem+".pdf")
            if run.returncode == 0 and pdf.exists() and pdf.stat().st_size > 100 and verify_magic(pdf,".pdf"):
                shutil.copy2(pdf,target)
                return True
        except (subprocess.TimeoutExpired, OSError):
            pass
    return False

def main():
    out = Path("weekly-data")
    out.mkdir(exist_ok=True)
    index = out/"index.json"
    try:
        previous = json.loads(index.read_text(encoding="utf-8"))
    except Exception:
        previous = {}
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        session = requests.Session()
        session.headers.update({"User-Agent":"YunseulClassroomPreview/1.0", "Accept-Language":"ko-KR,ko;q=0.9"})
        response = session.get(LIST_URL, timeout=30)
        response.raise_for_status()
        if response.encoding in (None,"ISO-8859-1"):
            response.encoding = response.apparent_encoding
        posts = posts_from(response.text, dt.date.today().year)
        # Public listing diagnostics: only post titles + link attributes, never student information.
        soup = BeautifulSoup(response.text, "html.parser")
        samples = []
        for row in soup.select("tr"):
            for anchor in row.select("a"):
                label = anchor.get_text(" ", strip=True)
                if re.search(r"1\s*학년", label) and re.search(r"\d{1,2}\s*월", label):
                    samples.append({"title":label[:100], "href":anchor.get("href","")[:200],
                                    "onclick":anchor.get("onclick","")[:200],
                                    "row_onclick":row.get("onclick","")[:200]})
                if len(samples) >= 4:
                    break
            if len(samples) >= 4:
                break
        (out / "parser-diagnostics.json").write_text(
            json.dumps({"candidates":samples,"parsed_posts":posts[:4],
                        "total_linked_posts":len(posts)},ensure_ascii=False,indent=2),
            encoding="utf-8")
        if not posts:
            raise ValueError("공개 게시판에서 날짜 및 링크가 확인되는 1학년 게시글을 찾지 못했습니다.")
        kept = {i["week"]:i for i in previous.get("items",[]) if isinstance(i,dict) and i.get("week")}
        for post in posts[:8]:
            week = post["week"]
            if week in kept and kept[week].get("source_url") == post["source_url"] and kept[week].get("preview_url"):
                continue
            detail = session.get(post["source_url"], timeout=25)
            detail.raise_for_status()
            item = dict(post, preview_url=None, preview_type=None, filename=None, note="게시글의 미리보기 가능 첨부파일을 찾지 못했습니다.")
            for attachment in attachments_from(detail.text):
                if not allowed(attachment["url"]):
                    continue
                try:
                    res = session.get(attachment["url"], timeout=40, stream=True, allow_redirects=False)
                    if res.status_code != 200 or "text/html" in res.headers.get("content-type","").lower():
                        continue
                    ext = suffix_of(res, attachment["name"])
                    if ext not in (".pdf",".png",".jpg",".jpeg",".webp",".hwp",".hwpx"):
                        continue
                    folder = out/week
                    folder.mkdir(exist_ok=True)
                    original = folder/("original"+ext)
                    total = 0
                    with original.open("wb") as f:
                        for chunk in res.iter_content(chunk_size=131072):
                            total += len(chunk)
                            if total > 20_000_000:
                                raise ValueError("첨부파일 크기 제한 초과")
                            f.write(chunk)
                    if total < 100 or not verify_magic(original,ext):
                        original.unlink(missing_ok=True)
                        continue
                    preview = original
                    if ext in (".hwp",".hwpx"):
                        preview = folder/"preview.pdf"
                        if not convert_document(original, preview):
                            item["note"] = "HWP 파일의 자동 PDF 변환을 지원하지 못했습니다. 원본 게시글을 확인하세요."
                            continue
                    item.update(preview_url=f"weekly-data/{week}/{preview.name}",
                        preview_type="pdf" if preview.suffix == ".pdf" else "image",
                        filename=preview.name, note=None)
                    break
                except (requests.RequestException,ValueError,OSError) as e:
                    logging.warning("첨부파일 처리 실패 %s: %s",week,e)
            kept[week] = item
        result = {"status":"ok","checked_at":timestamp,"board_url":LIST_URL,
                  "items":sorted(kept.values(), key=lambda x:x["week"], reverse=True)[:12],
                  "message":None}
    except Exception as e:
        logging.exception("주간학습안내 자동 수집 실패")
        result = {"status":"error","checked_at":timestamp,"board_url":LIST_URL,
                  "items":previous.get("items",[]),"message":str(e)[:180]}
    index.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":result["status"],"count":len(result["items"]),"message":result["message"]},ensure_ascii=False))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
