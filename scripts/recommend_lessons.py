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


CORE_GUIDES = {
    "math-pattern": {
        "headline": "수학 비밀 암호 제작소",
        "hook": "숫자가 지나가는 길에 어떤 비밀 규칙이 숨어 있을까요?",
        "minutes": 25,
        "materials": ["작은 수 카드", "칠판 또는 종이", "연필"],
        "steps": [["5분","규칙 발견","1, 3, 5, 7처럼 수의 변화에 대해 이야기해요."],
                  ["10분","나만의 규칙","수 또는 모양을 이용해 규칙 배열을 만들어요."],
                  ["10분","친구에게 도전","친구가 내가 만든 규칙을 알아맞혀요."]],
        "teacher_tip": "단순 암기보다 어떤 점이 반복되거나 달라지는지 말로 설명하게 해요.",
        "support": "다른 수 카드 3장만 제시한 뒤 이어지는 수를 골라 보게 해요.",
        "spark": ["다음 모양을 친구가 맞히게 만들려면?", "2씩 커지는 수를 만들면?", "나만의 비밀 규칙을 만든다면?"]
    },
    "math-calculation": {
        "headline": "우리 반 수학 가게",
        "hook": "물건을 사고팔며 덧셈과 뺄셈을 생활 속에서 써 봐요.",
        "minutes": 25,
        "materials": ["숫자 카드", "지우개 또는 종이 물건 카드"],
        "steps": [["5분","가게 준비","가짜 물건과 가격을 정해요."],
                  ["10분","계산 놀이","두 물건의 가격을 더하거나 남은 수량을 빼요."],
                  ["10분","수학 설명","내가 어떻게 계산했는지 그림·말로 설명해요."]],
        "teacher_tip": "사용할 수 범위를 학생의 학습 상태에 맞추고 계산 방식은 다양하게 인정해요.",
        "support": "실물 수 모형으로 먼저 계산해 보게 해요.",
        "spark": ["사과 3개에 2개가 더 생기면?", "10개 중 4개를 나누어 주면?", "내가 사장이라면 가격을 어떻게 정할까?"]
    },
    "korean-word": {
        "headline": "낱말 보물찾기",
        "hook": "교실 속 물건 이름을 찾아 소리 내어 읽어 봐요.",
        "minutes": 20,
        "materials": ["낱말 카드", "작은 상자(선택)"],
        "steps": [["5분","보물 탐색","친구와 주변 물건 이름을 찾고 말해요."],
                  ["10분","낱말 짝 찾기","그림과 낱말을 짝지어 읽어요."],
                  ["5분","보물 발표","찾은 낱말을 한 가지씩 소리 내어 읽어요."]],
        "teacher_tip": "교과서 낱말을 그대로 복제하지 않고 친숙한 새 예시 낱말로 연습해요.",
        "support": "그림 카드에 첫 글자를 함께 제시해요.",
        "spark": ["우리 교실에서 ‘가’로 시작하는 물건은?", "소리가 비슷한 낱말을 찾는다면?"]
    },
    "korean-sentence": {
        "headline": "문장 수리소",
        "hook": "친구들이 쉽게 읽을 수 있는 문장을 만들어 보자.",
        "minutes": 20,
        "materials": ["짧은 문장 카드", "연필"],
        "steps": [["5분","문장 읽기","짧은 문장을 천천히 소리 내어 읽어요."],
                  ["10분","문장 바꾸기","누가·언제·어디에서를 바꾸어 새 문장을 만들어 봐요."],
                  ["5분","낭독 시간","만든 문장을 친구에게 읽어 줘요."]],
        "teacher_tip": "초1 수준에서는 한 문장씩 정확하고 자연스럽게 읽는 것을 먼저 연습해요.",
        "support": "문장틀 ‘나는 ○○에서 ○○했어요.’를 제공해요.",
        "spark": ["‘토끼가 놀아요.’에서 장소를 바꾸면?", "친구가 쉽게 읽으려면 어떻게 쓸까?"]
    },
    "korean-meaning": {
        "headline": "이야기 탐정단",
        "hook": "글 속에 숨은 단서를 찾아 ‘왜?’ 질문에 답해 보자.",
        "minutes": 20,
        "materials": ["짧은 이야기 카드 또는 읽기 게임"],
        "steps": [["5분","예상하기","제목이나 첫 문장을 듣고 내용을 예상해요."],
                  ["10분","단서 찾기","누가·어디서·왜를 찾아 읽어요."],
                  ["5분","한 문장 나누기","글을 읽고 알게 된 점을 말해요."]],
        "teacher_tip": "교과서 원문이 아닌 직접 만든 짧은 이야기로 확장 연습해요.",
        "support": "질문을 듣고 그림·말로 답할 수 있어요.",
        "spark": ["주인공은 왜 그렇게 했을까?", "이야기의 다음 장면을 그린다면?"]
    },
}


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
                    **CORE_GUIDES.get(rule["id"], {}),
                })
            # '상상 1-2' / '이야기 1-2' are integrated textbook themes.
            # A suggestion appears ONLY if the book label and its literal topic
            # are both visible in the original PDF (page 1).
            catalog_file = Path("lesson-catalog.json")
            if catalog_file.exists():
                catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
                for activity in catalog.get("activities", []):
                    book = activity.get("book", "")
                    if not re.search(re.escape(book).replace(r"\ ", r"\s*"), text):
                        continue
                    evidence = find_evidence(text, activity.get("source_patterns", []))
                    if not evidence:
                        continue
                    extra = activity.get("extra_patterns", [])
                    if extra and not find_evidence(text, extra):
                        continue
                    recs.append({
                        "id": activity["id"],
                        "subject": activity["subject"],
                        "book": book,
                        "strand": activity.get("strand"),
                        "topic": activity["topic"],
                        "icon": activity.get("icon", "🎨"),
                        "evidence": evidence,
                        "source_page": 1,
                        "why": "주간학습안내에서 확인한 통합교과 주제와 연결된 창작·놀이 활동이에요.",
                        "actions": [{"id":"lesson-print", "label":"🖨️ 활동지 출력"}],
                        "headline": activity["headline"],
                        "hook": activity.get("hook", ""),
                        "minutes": activity.get("minutes", 35),
                        "materials": activity.get("materials", []),
                        "steps": activity.get("steps", []),
                        "teacher_tip": activity.get("teacher_tip", ""),
                        "support": activity.get("support", ""),
                        "sheet": activity.get("sheet", {}),
                        "spark": activity.get("spark", []),
                    })
            # Let the new integrated activities appear first on the home feed.
            order = {"상상":0,"이야기":1,"국어":2,"수학":3}
            recs.sort(key=lambda r:(order.get(r["subject"], 9),r["topic"]))
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
