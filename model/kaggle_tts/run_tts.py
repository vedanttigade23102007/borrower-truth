"""Narration for the two videos, spoken by an open-weights voice model on a free Kaggle machine.

RUNS ON KAGGLE. Kokoro-82M (Apache-2.0) turns each narration line into a WAV. Nothing is installed
on the laptop; the WAVs are downloaded and laid under the screen recordings by
application/videos/tools/.

Input: lines.json in the private dataset (borrower-truth-narration), a list of
       {"id": "tr01", "text": "..."} in speaking order.
Output: /kaggle/working/narration/<id>.wav plus index.json with each line's duration.
"""
import glob
import json
import os
import subprocess
import sys
import wave

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "kokoro>=0.9", "soundfile"], check=True)
subprocess.run(["apt-get", "install", "-y", "-qq", "espeak-ng"], check=False)

import soundfile as sf  # noqa: E402
from kokoro import KPipeline  # noqa: E402

VOICE = os.environ.get("BT_VOICE", "af_heart")  # a calm American English voice
SPEED = 0.98

hits = glob.glob("/kaggle/input/**/lines.json", recursive=True)
lines = json.load(open(hits[0]))
out_dir = "/kaggle/working/narration"
os.makedirs(out_dir, exist_ok=True)

pipe = KPipeline(lang_code="a")
index = []
for item in lines:
    path = os.path.join(out_dir, f"{item['id']}.wav")
    chunks = [audio for _, _, audio in pipe(item["text"], voice=VOICE, speed=SPEED)]
    audio = chunks[0] if len(chunks) == 1 else __import__("numpy").concatenate(chunks)
    sf.write(path, audio, 24000)
    with wave.open(path) as w:
        secs = round(w.getnframes() / w.getframerate(), 2)
    index.append(dict(id=item["id"], seconds=secs, words=len(item["text"].split())))
    print(f"{item['id']}: {secs:>5.2f}s · {item['text'][:70]}", flush=True)

json.dump(dict(voice=VOICE, speed=SPEED, lines=index), open(os.path.join(out_dir, "index.json"), "w"), indent=1)
print("total:", round(sum(x["seconds"] for x in index), 1), "s")
