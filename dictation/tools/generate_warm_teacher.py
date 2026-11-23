#!/usr/bin/env python3
"""Create a DISTINCT warm Korean teacher voice using Qwen3-TTS 1.7B.

This uses style instructions that the 0.6B CustomVoice model does not support.
Writes ONLY voice/WARM1; existing F1/M1/F2/M2/S1/MELO/COSY3/GPTSOVITS
recordings are never overwritten or used as substitutes.
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "voice-manifest.json").read_text(encoding="utf-8"))
DEST = ROOT / "voice" / "WARM1"
STYLE = (
    "Speak Korean like a caring, friendly first-grade teacher reading gently "
    "to children. Sound sincerely warm, approachable, relaxed and reassuring, "
    "not prim, aloof or formal. Use normal conversational speed and clear "
    "pronunciation. Keep natural, soft intonation and end each short sentence "
    "with a gentle, smooth cadence, never a sudden pitch drop. "
    "Do not whisper, exaggerate emotions, sing, or sound robotic."
)


def all_phrases():
    data = []
    for grade in range(1, 15):
        sentences = MANIFEST["grades"][str(grade)]
        assert len(sentences) == 10, f"Missing sentence in grade {grade}"
        for idx, text in enumerate(sentences, 1):
            data.append((f"g{grade:02d}_{idx:02d}", text))
    for key, text in MANIFEST["extras"].items():
        data.append((key, text))
    assert len(data) == 172, len(data)
    assert len({key for key, _ in data}) == 172
    return data


def spoken(text, key):
    # Narration-only adjustment; never modify the original dictation text.
    # Short numeric labels can be cut off by an autoregressive TTS model;
    # read "7번 문제입니다." instead of the awkward isolated "7번.".
    if key.startswith("n") and key[1:].isdigit():
        return str(int(key[1:])) + "번 문제입니다."
    text = text.strip()
    return text if text and text[-1] in ".!?…。”’\"" else text + "."


def render_one(model, key, text, out, sr_converter):
    import soundfile as sf
    import torch
    with torch.inference_mode():
        wavs, sr = model.generate_custom_voice(
            text=spoken(text, key), language="Korean", speaker="Sohee", instruct=STYLE
        )
    if not wavs or len(wavs[0]) < int(sr * 0.3):
        raise RuntimeError(f"Empty or extremely short audio generated: {key}")
    if len(wavs[0]) > int(sr * 35):
        raise RuntimeError(f"Unusually long audio, review hallucination: {key}")
    with tempfile.TemporaryDirectory(prefix="warm-teacher-production-") as tmp:
        wavpath = pathlib.Path(tmp) / "narration.wav"
        sf.write(str(wavpath), wavs[0], sr)
        subprocess.run(
            [sr_converter, "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(wavpath), "-vn", "-ac", "1", "-c:a", "libmp3lame",
             "-q:a", "4", str(out)], check=True,
        )
    if not out.is_file() or out.stat().st_size < 2000:
        raise RuntimeError(f"MP3 missing or invalid: {out}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--shard", type=int, required=True)
    p.add_argument("--shards", type=int, default=8)
    args = p.parse_args()
    if not (0 <= args.shard < args.shards):
        raise ValueError("Invalid shard index")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    items = [(i, k, t) for i, (k, t) in enumerate(all_phrases()) if i % args.shards == args.shard]
    assert items
    DEST.mkdir(parents=True, exist_ok=True)
    # Always synthesize NEW audio; reusing old clips would defeat the warm-style change.
    todo = [(idx, key, text) for idx, key, text in items if not (DEST / f"{key}.mp3").exists()]
    print(f"Warm shard {args.shard + 1}/{args.shards}: {len(items)} clips ({len(todo)} to synthesize).", flush=True)
    if not todo: return

    import torch
    import imageio_ffmpeg
    from qwen_tts import Qwen3TTSModel
    torch.set_num_threads(3)
    model = Qwen3TTSModel.from_pretrained(
        "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        device_map="cpu", dtype=torch.float32, attn_implementation="sdpa",
    )
    for pos, (idx, key, text) in enumerate(todo, 1):
        start = time.monotonic()
        torch.manual_seed(410000 + idx)
        try:
            render_one(model, key, text, DEST / f"{key}.mp3", imageio_ffmpeg.get_ffmpeg_exe())
        except Exception:
            print(f"Failed at {key} with prompt: {text}", flush=True)
            raise
        print(f"Warm shard {args.shard}: {pos}/{len(todo)} {key} ({time.monotonic()-start:.1f}s)", flush=True)
    print(f"Completed shard {args.shard}: {len(items)} clips.", flush=True)


if __name__ == "__main__":
    main()
