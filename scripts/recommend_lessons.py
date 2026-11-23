#!/usr/bin/env python3
"""Recommend existing first-grade classroom activities from a verified public weekly PDF.
Only literal text matching is used. Never fabricate an achievement standard or textbook text.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
from pathlib import Path

import fitz

ROOT = Path("weekly-data")
INDEX = ROOT / "index.json"
OUTPUT = ROOT / "lesson-recommendations.json"

# Literal or spacing-tolerant snippets supported by the school's weekly schedule.
# A recommendation is present ONLY when its source expression occurs in that week's PDF.
RULES = [
    {
        "id": "math-pattern", "subject": "수학",
        "topic": "규칙 찾기·만들기", "icon": "🔺",
        "patterns": [r"규칙을\s*찾아볼까요", r"규칙을\s*만들어\s*볼까요", r"규칙\s*찾기", r"규칙\s*만들기"],
        "why": "주간학습안내의 규칙 활동과 관련된 수 배열 규칙 문제를 연습해요. 교과서 문항을 그대로 옮긴 것은 아니에요.",
        "actions": [{"id":"worksheet-pattern", "label":"📝 규칙 학습지 20문제"}, {"id":"math-pattern", "label":"🎮 수학 탐정 규칙 게임"}],
    },
    {
        "id": "math-calculation", "subject": "수학",
        "topic": "덧셈과 뺄셈 연습", "icon": "➕",
        "patterns": [r"덧셈과\s*뺄셈\s*문제\s*풀기", r"덧셈과\s*뺄셈", r"덧셈\s*문제\s*풀기", r"뺄셈\s*문제\s*풀기"],
        "why": "주간학습안내에 나온 계산 활동과 연결되는 별도 연습 문제예요.",
        "actions": [{"id":"worksheet-math", "label":"📝 덧셈·뺄셈 학습지"}],
    },
    {
        "id": "korean-word", "subject": "국어",
        "topic": "낱말 바르게 읽기", "icon": "🔤",
        "patterns": [r"낱말을\s*바르게\s*쓰고\s*읽", r"낱말을\s*바르게\s*읽", r"낱말\s*읽기"],
        "why": "교과서 원문 대신 새로운 연습 낱말로 읽기·듣기를 연습해요.",
        "actions": [{"id":"reading-word", "label":"🔊 낱말 읽기 게임"}],
    },
    {
        "id": "korean-sentence", "subject": "국어",
        "topic": "문장 바르게 읽기", "icon": "✏️",
        "patterns": [r"문장을\s*바르게\s*쓰고\s*읽", r"문장을\s*바르게\s*읽", r"문장\s*읽기"],
        "why": "교과서의 문장과 별개인 짧은 문장 읽기 활동으로 연결해요.",
        "actions": [{"id":"reading-short", "label":"🔊 짧은 문장 읽기"}],
    },
    {
        "id": "korean-meaning", "subject": "국어",
        "topic": "글의 의미 생각하며 읽기", "icon": "📖",
        "patterns": [r"글의\s*의미를\s*생각하며", r"글의\s*뜻을\s*생각하며", r"글의\s*내용을\s*생각하며"],
        "why": "새로 만든 짧은 이야기의 내용을 읽고 질문에 답하는 확장 활동이에요. 교과서 본문은 포함하지 않아요.",
        "actions": [{"id":"reading-meaning", "label":"💡 읽기 이해 미션"}],
    },
]


def find_evidence(page_text: str, patterns: list[str]) -> list[str]:
    found: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, page_text, re.I | re.M):
            snippet = " ".join(match.group(0).split())
            if snippet and snippet not in found:
                found.append(snippet[:80])
            if len(found) >= 3:
                return found
    return found


def lessons_for_pdf(path: Path) -> tuple[str, list[dict], str | None]:
    try:
        with fitz.open(path) as doc:
            # Page one contains the general grade-1 weekly class activities;
            # following pages may list class-specific room schedules.
            if not len(doc):
                return "needs_review", [], "PDF에 페이지가 없습니다."
            text = doc[0].get_text("text", sort=True)
            if not text.strip():
                return "needs_review", [], "스캔 PDF라 수업 내용을 텍스트로 읽지 못했습니다."
            if "주간학습" not in text and "1학년" not in text:
                return "needs_review", [], "1학년 주간학습안내 문서인지 확인이 필요합니다."
            recs = []
            for rule in RULES:
                evidence = find_evidence(text, rule["patterns"])
                if not evidence:
                    continue
                recs.append({
                    "id": rule["id"],
                    "subject": rule["subject"],
                    "topic": rule["topic"],
                    "icon": rule["icon"],
                    "evidence": evidence,
                    "source_page": 1,
                    "why": rule["why"],
                    "actions": rule["actions"],
                })
            return "ok", recs, None
    except Exception as exc:
        logging.exception("PDF에서 수업 내용을 추출하지 못함: %s",path)
        return "needs_review", [], f"PDF 분석 실패: {type(exc).__name__}"


def main() -> None:
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    weeks = {}
    for item in data.get("items", [])[:12]:
        week = item.get("week")
        preview = item.get("preview_url", "")
        if not isinstance(week,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",week):
            continue
        path = Path(preview)
        # Never read out-of-tree paths or untrusted file URLs.
        expected = ROOT / week
        if not str(path).startswith(str(expected) + "/") or path.suffix.lower() != ".pdf":
            weeks[week] = {"status":"needs_review","source_pdf":None,
                           "recommendations":[],"message":"PDF가 없어 수업 내용을 확인할 수 없습니다."}
            continue
        if not path.exists():
            weeks[week] = {"status":"needs_review","source_pdf":None,
                           "recommendations":[],"message":"PDF 파일을 찾을 수 없습니다."}
            continue
        status, recs, message = lessons_for_pdf(path)
        weeks[week] = {"status":status,"source_pdf":preview,"recommendations":recs,
                       "message":message,
                       "source_title":str(item.get("title","주간학습안내"))[:120]}
    result = {"version":1,"generated_at":now,"method":"literal_pdf_text_matching",
              "description":"학습안내의 표현을 확인한 뒤 기존 활동으로 연결하는 규칙 기반 추천. 교과서 원문 또는 성취기준 검증이 아닙니다.",
              "weeks":weeks}
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"weeks":len(weeks),"newest_week":next(iter(weeks),None),
                      "newest_recommendations":len(weeks.get(next(iter(weeks),""),{}).get("recommendations",[]))},ensure_ascii=False))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
