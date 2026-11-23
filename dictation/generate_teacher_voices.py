#!/usr/bin/env python3
"""Generate NEW 38.0 Korean classroom-teacher style narration clips.

Preservation policy:
- Do not write to, replace, regenerate, or delete F1/M1 (37.0 voices).
- Only create the distinct F2 and M2 presets under their own folders.
- Student rosters, exam results and private data must never be included.
"""
import json
import pathlib
import subprocess
import tempfile

ROOT=pathlib.Path(__file__).resolve().parent
MANIFEST=json.loads((ROOT/"voice-manifest.json").read_text(encoding="utf-8"))
DEST=ROOT/"voice"
# Supertonic 3 recommends speeds near 1.05 for naturally flowing speech.
# Slightly measured pacing is appropriate for young learners.
NEW_VOICES={
  "F2":{"speed":1.02,"description":"부드러운 여성 선생님"},
  "M2":{"speed":1.03,"description":"차분한 남성 선생님"},
}
TOTAL_STEPS=12  # Highest documented quality setting; never modify F1/M1 originals.


def utterances():
    for grade in range(1,15):
        group=MANIFEST["grades"][str(grade)]
        assert len(group)==10,(grade,len(group))
        for index,text in enumerate(group,1):
            yield f"g{grade:02d}_{index:02d}",text
    for key,text in MANIFEST["extras"].items():
        yield key,text


def spoken_text(original):
    """Only add a closing pause marker to bare fragments during synthesis.

    Never alter dictation's displayed source text or change any spoken word.
    """
    text=original.strip()
    if text and text[-1] not in ".!?…。”’\"":
        return text+"."
    return text


def synthesize(tts,style,text,output,speed):
    import imageio_ffmpeg
    # This is a speech-model inference control, not a browser playback-rate hack:
    wav,_=tts.synthesize(
        spoken_text(text),voice_style=style,lang="ko",
        total_steps=TOTAL_STEPS,speed=speed,
    )
    with tempfile.TemporaryDirectory(prefix="teacher-voice-") as tmp:
        wavfile=pathlib.Path(tmp)/"source.wav"
        tts.save_audio(wav,str(wavfile))
        cmd=[
            imageio_ffmpeg.get_ffmpeg_exe(),"-hide_banner","-loglevel","error","-y",
            "-i",str(wavfile),"-vn","-ac","1","-ar","44100",
            "-c:a","libmp3lame","-q:a","4","-af","apad=pad_dur=0.23",
            str(output),
        ]
        subprocess.run(cmd,check=True)
    if not output.exists() or output.stat().st_size<1200:
        raise RuntimeError(f"Could not create audio: {output}")


def main():
    from supertonic import TTS
    source=list(utterances())
    assert len(source)==172,len(source)
    print("Preparing independent teacher voice presets (never touching F1/M1).",flush=True)
    tts=TTS(auto_download=True)
    for voice,settings in NEW_VOICES.items():
        folder=DEST/voice
        folder.mkdir(parents=True,exist_ok=True)
        style=tts.get_voice_style(voice_name=voice)
        for i,(key,txt) in enumerate(source,1):
            out=folder/(key+".mp3")
            if out.exists() and out.stat().st_size>1200:
                continue
            synthesize(tts,style,txt,out,settings["speed"])
            if i==1 or i%10==0 or i==len(source):
                print(f"{voice} {i}/{len(source)} rendered: {txt[:30]}",flush=True)
    print("Completed 344 independent teacher-style clips; original 37.0 voices unchanged.",flush=True)


if __name__=="__main__":
    main()
