#!/usr/bin/env python3
"""Generate MeloTTS Korean dictation audio from the site's original sentences."""
import re, json, pathlib, subprocess, tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
html=(ROOT/"index.html").read_text(encoding="utf-8")
# Extract original sentences from JS by evaluating only the ORIGINAL literal in Node.
start=re.search(r'\bconst\s+ORIGINAL\s*=\s*',html)
if not start: raise RuntimeError("ORIGINAL sentence data not found")
i=start.end(); depth=0; quote=None; esc=False; end=None
for j in range(i,len(html)):
    c=html[j]
    if quote:
        if esc: esc=False
        elif c=="\\": esc=True
        elif c==quote: quote=None
    elif c in "'\"`": quote=c
    elif c in "[{": depth+=1
    elif c in "]}":
        depth-=1
        if depth==0: end=j+1; break
if end is None: raise RuntimeError("Unclosed ORIGINAL literal")
expr=html[i:end]
with tempfile.NamedTemporaryFile(mode="w",suffix=".js",encoding="utf-8") as f:
    f.write("const ORIGINAL = "+expr+"; process.stdout.write(JSON.stringify(ORIGINAL));")
    f.flush()
    original=json.loads(subprocess.check_output(["node",f.name],text=True))
from melo.api import TTS
import soundfile as sf
model=TTS(language="KR",device="cpu")
speaker=model.hps.data.spk2id["KR"]
out=ROOT/"voice"/"MELO"
out.mkdir(parents=True,exist_ok=True)
sentences=[]
for grade in range(1,15):
    lines=original[str(grade)]
    if len(lines)!=10: raise ValueError(f"grade {grade}: expected 10 lines, got {len(lines)}")
    for n,line in enumerate(lines,1):
        sentences.append((f"g{grade:02d}_{n:02d}",line))
sentences += [("intro","시험을 시작하겠습니다."),("outro","시험을 종료합니다.")]
sentences += [(f"n{n:02d}",f"{n}번.") for n in range(1,31)]
for idx,(name,line) in enumerate(sentences,1):
    target=out/(name+".mp3")
    if target.exists(): continue
    wav=out/(name+".wav")
    model.tts_to_file(line,speaker,str(wav),speed=1.0)
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(wav),"-codec:a","libmp3lame","-qscale:a","4",str(target)],check=True)
    wav.unlink()
    print(f"{idx}/{len(sentences)} {name}: {line}",flush=True)
print(f"Generated {len(sentences)} files in {out}")
