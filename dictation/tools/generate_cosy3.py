#!/usr/bin/env python3
"""CosyVoice3 Korean synthesis, using existing Qwen-generated S1 as licensed reference.

Only writes voice/COSY3; original voice clips and their source manifest are never edited.
"""
import argparse,json,pathlib,subprocess,sys,tempfile,time,os
ROOT=pathlib.Path(__file__).resolve().parents[1]
MANIFEST=json.loads((ROOT/"voice-manifest.json").read_text(encoding="utf-8"))
parser=argparse.ArgumentParser()
parser.add_argument("--shard",type=int,required=True)
parser.add_argument("--shards",type=int,default=8)
args=parser.parse_args()
assert 0<=args.shard<args.shards
sys.path[:0]=[str(pathlib.Path("_cosyvoice").resolve()),str(pathlib.Path("_cosyvoice/third_party/Matcha-TTS").resolve())]
from cosyvoice.cli.cosyvoice import AutoModel
import torchaudio
from huggingface_hub import snapshot_download
model_dir=pathlib.Path("_cosyvoice/pretrained_models/Fun-CosyVoice3-0.5B")
snapshot_download("FunAudioLLM/Fun-CosyVoice3-0.5B-2512",local_dir=str(model_dir))
reference=ROOT/"voice"/"S1"/"g01_05.mp3"
if not reference.is_file():raise RuntimeError("Original Sohee reference is unavailable")
with tempfile.TemporaryDirectory(prefix="cosy3-") as tmp:
    prompt=pathlib.Path(tmp)/"reference.wav"
    subprocess.run(["ffmpeg","-loglevel","error","-y","-i",str(reference),"-ac","1","-ar","16000",str(prompt)],check=True)
    model=AutoModel(model_dir=str(model_dir))
    items=[]
    for grade in range(1,15):
        for num,text in enumerate(MANIFEST["grades"][str(grade)],1): items.append((f"g{grade:02d}_{num:02d}",text))
    items.extend(MANIFEST["extras"].items())
    assert len(items)==172
    out=ROOT/"voice"/"COSY3"
    out.mkdir(parents=True,exist_ok=True)
    for i,(key,text) in enumerate(items):
        if i%args.shards != args.shard:continue
        target=out/(key+".mp3")
        if target.exists() and target.stat().st_size>2000:continue
        if key.startswith("n") and key[1:].isdigit(): utterance=f"{int(key[1:])}번 문제입니다."
        else: utterance=text if text.endswith((".","!","?","。","”","’")) else text+"."
        wave=None
        for chunk in model.inference_zero_shot(utterance,"You are a helpful assistant.<|endofprompt|>꽃이 활짝 피었습니다.",str(prompt),stream=False):
            part=chunk["tts_speech"].detach().cpu()
            wave=part if wave is None else __import__("torch").cat([wave,part],dim=-1)
        if wave is None or wave.numel()<model.sample_rate//3:raise RuntimeError(f"No audio: {key}")
        intermediate=pathlib.Path(tmp)/(key+".wav")
        torchaudio.save(str(intermediate),wave,model.sample_rate)
        subprocess.run(["ffmpeg","-loglevel","error","-y","-i",str(intermediate),"-ac","1","-codec:a","libmp3lame","-q:a","4",str(target)],check=True)
        intermediate.unlink()
        if target.stat().st_size<2000:raise RuntimeError(f"Too small: {key}")
        print(f"CosyVoice3 shard {args.shard}: {key} {text}",flush=True)
