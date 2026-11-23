#!/usr/bin/env python3
"""Generate reusable Korean AI narration assets for Dictation Kingdom.
The generated MP3 files contain only public dictation phrases (not student data).
Supertonic 3 weights: OpenRAIL-M (Supertone Inc.).
"""
import json
import os
import pathlib
import subprocess
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "voice-manifest.json").read_text(encoding="utf-8"))
TARGET = ROOT / "voice"
VOICES = ("F1", "M1")


def phrases():
    for grade in range(1, 15):
        group = MANIFEST["grades"][str(grade)]
        assert len(group) == 10, f"Expected 10 sentences in grade {grade}"
        for index, text in enumerate(group, 1):
            yield f"g{grade:02d}_{index:02d}", text
    for key, text in MANIFEST["extras"].items():
        yield key, text


def make_mp3(tts, style, text, output):
    import imageio_ffmpeg
    with tempfile.TemporaryDirectory(prefix="dictation-tts-") as tmp:
        wav_path = pathlib.Path(tmp) / "speak.wav"
        audio, duration = tts.synthesize(text, voice_style=style, lang="ko")
        tts.save_audio(audio, str(wav_path))
        subprocess.run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(wav_path),
                "-vn", "-c:a", "libmp3lame", "-q:a", "5", "-ar", "24000",
                str(output),
            ],
            check=True,
        )
    if not output.exists() or output.stat().st_size < 1000:
        raise RuntimeError(f"Audio asset too small: {output}")
    return duration


def main():
    from supertonic import TTS

    phrases_to_generate = list(phrases())
    assert len(phrases_to_generate) == 172, len(phrases_to_generate)
    print("Loading Supertone Supertonic 3 model...", flush=True)
    tts = TTS(auto_download=True)
    for voice in VOICES:
        style = tts.get_voice_style(voice_name=voice)
        folder = TARGET / voice
        folder.mkdir(parents=True, exist_ok=True)
        for idx, (key, text) in enumerate(phrases_to_generate, 1):
            output = folder / f"{key}.mp3"
            if output.is_file() and output.stat().st_size > 1000:
                continue
            duration = make_mp3(tts, style, text, output)
            if idx % 10 == 0 or idx == 1 or idx == len(phrases_to_generate):
                print(f"{voice} {idx}/{len(phrases_to_generate)}: {text[:22]} ({duration:.1f}s)", flush=True)
    print("Generated all required natural Korean speech clips.", flush=True)


if __name__ == "__main__":
    main()
