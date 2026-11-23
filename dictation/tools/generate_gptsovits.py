#!/usr/bin/env python3
"""Create actual GPT-SoVITS v2 Korean narrations (not browser speech) on CPU.

Uses the existing AI-generated Sohee phrases as a reference recording.
Never edits F1/M1/F2/M2/S1 original voice files.
"""
import json,pathlib,subprocess,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/"voice-manifest.json").read_text(encoding="utf-8"))
sys.path.insert(0,str(pathlib.Path("_gptsovits").resolve()))
from huggingface_hub import snapshot_download
import soundfile as sf
import numpy as np
model_dir=pathlib.Path("_gptsovits/GPT_SoVITS/pretrained_models")
snapshot_download("lj1995/GPT-SoVITS",local_dir=str(model_dir),allow_patterns=[
    "gsv-v2final-pretrained/*",
    "chinese-hubert-base/*",
    "chinese-roberta-wwm-ext-large/*",
])
required=[
    model_dir/"gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt",
    model_dir/"gsv-v2final-pretrained/s2G2333k.pth",
]
for p in required:
    if not p.exists():raise RuntimeError(f"GPT-SoVITS pretrained model missing: {p}")
from GPT_SoVITS.TTS_infer_pack.TTS import TTS,TTS_Config
config={"custom":dict(TTS_Config.default_configs["v2"],device="cpu",is_half=False)}
tts=TTS(TTS_Config(config))
items=[]
for grade in range(1,15):
    for n,line in enumerate(manifest["grades"][str(grade)],1): items.append((f"g{grade:02d}_{n:02d}",line))
items.extend(manifest["extras"].items())
assert len(items)==172
reference=[ROOT/"voice"/"S1"/k for k in ("g01_05.mp3","g04_02.mp3","g02_06.mp3")]
for f in reference:
    if not f.is_file():raise RuntimeError(f"Missing authorized AI reference: {f}")
out=ROOT/"voice"/"GPTSOVITS"
out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix="gptsovits-") as temp:
    ref=pathlib.Path(temp)/"reference.wav"
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-y"]
    for file in reference:cmd.extend(["-i",str(file)])
    cmd.extend(["-filter_complex","[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]","-map","[out]","-ar","32000","-ac","1",str(ref)])
    subprocess.run(cmd,check=True)
    prompt="꽃이 활짝 피었습니다. 학교 운동장이 넓다. 성이 와장창 무너졌어."
    for idx,(key,line) in enumerate(items,1):
        target=out/(key+".mp3")
        if target.exists() and target.stat().st_size>2000:continue
        utterance=f"{int(key[1:])}번 문제입니다." if key.startswith("n") and key[1:].isdigit() else line
        if utterance[-1] not in ".!?…。”’\"":utterance+="."
        request={"text":utterance,"text_lang":"ko",
                 "ref_audio_path":str(ref),"prompt_text":prompt,"prompt_lang":"ko",
                 "text_split_method":"cut0","batch_size":1,"speed_factor":1.0,
                 "streaming_mode":False,"use_cuda_graph":False,"parallel_infer":False}
        output=tts.run(request)
        chunks=[]
        samplerate=None
        for sr,wav in output:
            samplerate=sr
            chunks.append(np.asarray(wav).reshape(-1))
        if not chunks or samplerate is None:raise RuntimeError(f"Generated no speech: {key}")
        wav=np.concatenate(chunks)
        if len(wav)<samplerate//3:raise RuntimeError(f"Too short: {key}")
        interim=pathlib.Path(temp)/"render.wav"
        sf.write(str(interim),wav,samplerate)
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(interim),"-codec:a","libmp3lame","-q:a","4",str(target)],check=True)
        if target.stat().st_size<2000:raise RuntimeError(f"Missing MP3: {key}")
        print(f"GPT-SoVITS: {idx}/{len(items)} {key} {line}",flush=True)
