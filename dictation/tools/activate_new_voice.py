#!/usr/bin/env python3
"""Add a new voice choice ONLY after all 172 real audio files exist.

Never modifies any existing voice file. The hosted site can play an MP3
without API keys; it must not advertise voices that have not been rendered.
"""
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=json.loads((ROOT/"voice-manifest.json").read_text(encoding="utf-8"))
VOICE_NAMES={
    "MELO": "MeloTTS · 한국어 낭독",
    "COSY3": "CosyVoice 3 · 자연스러운 선생님",
    "GPTSOVITS": "GPT-SoVITS · 선생님 낭독",
    "WARM1": "다정한 선생님 · 부드러운 억양 (NEW)",
}
a=argparse.ArgumentParser()
a.add_argument("voice",choices=VOICE_NAMES)
args=a.parse_args()
voice=args.voice
directory=ROOT/"voice"/voice
expected={f"g{g:02d}_{k:02d}.mp3" for g in range(1,15) for k in range(1,11)}
expected.update(f"{key}.mp3" for key in MANIFEST["extras"])
actual={p.name for p in directory.glob("*.mp3")} if directory.exists() else set()
if len(expected)!=172 or actual!=expected:
    raise SystemExit(f"Refusing to publish {voice}: {len(actual)}/172 clips; missing={sorted(expected-actual)[:12]}")
for p in directory.glob("*.mp3"):
    if p.stat().st_size<2000: raise SystemExit(f"Invalid audio file: {p}")
    if shutil.which("ffprobe"):
        r=subprocess.run(["ffprobe","-v","error","-select_streams","a:0","-show_entries","stream=codec_name","-of","default=noprint_wrappers=1",str(p)],text=True,capture_output=True)
        if r.returncode or "codec_name=mp3" not in r.stdout:
            raise SystemExit(f"Unreadable MP3: {p}: {r.stderr[-300:]}")
index=ROOT/"index.html"
html=index.read_text(encoding="utf-8")
start=html.index('<select id="recordedVoice"')
end=html.index("</select>",start)
select=html[start:end]
if f'value="{voice}"' not in select:
    html=html[:end]+f'\n <optgroup label="새 자연스러운 한국어 목소리"><option value="{voice}">{VOICE_NAMES[voice]}</option></optgroup>'+html[end:]
    # Allow persisted voice choice and changing the selection.
    expression=r"\['F1','M1','F2','M2','S1'(?:,'(?:MELO|COSY3|GPTSOVITS|WARM1)')*\]"
    found=list(re.finditer(expression,html))
    if len(found)!=2: raise SystemExit(f"Unexpected recorded-voice allowlist count: {len(found)}")
    def add(m):
        return m.group(0)[:-1]+f",'{voice}']"
    html=re.sub(expression,add,html)
    index.write_text(html,encoding="utf-8")
print(f"Enabled {voice} with {len(actual)} verified MP3 files; old voices untouched.")
