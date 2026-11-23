#!/usr/bin/env python3
"""Try Qwen3-TTS Sohee Korean teacher voice with reproducible source sentences.

This script NEVER writes to the previously frozen F1/M1/F2/M2 voice folders.
It produces a 3-clip proof-of-concept in voice-candidates/S1.
"""
import json, os, pathlib, subprocess, tempfile, time

ROOT=pathlib.Path(__file__).resolve().parent
MANIFEST=json.loads((ROOT/"voice-manifest.json").read_text(encoding="utf-8"))
DEST=ROOT/"voice-candidates"/"S1"
TEST_KEYS=[(1,1),(1,5),(2,6)]


def main():
    import torch
    import soundfile as sf
    from qwen_tts import Qwen3TTSModel
    import imageio_ffmpeg
    os.environ.setdefault("TOKENIZERS_PARALLELISM","false")
    torch.set_num_threads(4)
    DEST.mkdir(parents=True,exist_ok=True)
    print("Loading Qwen3-TTS 0.6B CustomVoice, Korean native speaker Sohee",flush=True)
    started=time.time()
    model=Qwen3TTSModel.from_pretrained(
        "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        device_map="cpu",
        dtype=torch.float32,
        attn_implementation="sdpa",
    )
    print(f"Model ready after {time.time()-started:.1f}s",flush=True)
    for grade,item in TEST_KEYS:
        key=f"g{grade:02d}_{item:02d}"
        text=MANIFEST["grades"][str(grade)][item-1]
        # Oral narration punctuation only; written originals remain untouched.
        speak=text if text[-1] in ".!?…" else text+"."
        print(f"Synthesizing {key}: {speak}",flush=True)
        began=time.time()
        wavs,sr=model.generate_custom_voice(
            text=speak,language="Korean",speaker="Sohee"
        )
        if not wavs or not len(wavs[0]):
            raise RuntimeError(f"No speech audio for {key}")
        with tempfile.TemporaryDirectory(prefix="sohee-") as tmp:
            wav=pathlib.Path(tmp)/"source.wav"
            sf.write(str(wav),wavs[0],sr)
            out=DEST/(key+".mp3")
            subprocess.run([
                imageio_ffmpeg.get_ffmpeg_exe(),"-hide_banner","-loglevel","error","-y",
                "-i",str(wav),"-codec:a","libmp3lame","-q:a","4",str(out)
            ],check=True)
        if out.stat().st_size<2000:
            raise RuntimeError(f"Bad audio: {out}")
        print(f"Success {key}: {out.stat().st_size} bytes in {time.time()-began:.1f}s",flush=True)
    print("Three Korean Sohee clips created successfully",flush=True)


if __name__=="__main__":
    main()
