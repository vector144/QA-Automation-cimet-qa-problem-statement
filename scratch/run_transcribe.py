import sys
import asyncio
import os
import json
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.transcribe import transcribe_audio_file

async def main():
    for stem in ["3613793", "3613794"]:
        p = Path(f"audio/{stem}.mp3.mpeg")
        print(f"Transcribing {p}...")
        try:
            res = await transcribe_audio_file(p)
            print(f"SUCCESS {stem}: {len(res['turns'])} turns, duration={res['duration_sec']:.1f}s")
            # Save pre-generated transcript JSON as Option D backup!
            out_json = Path(f"data/transcript_{stem}.json")
            out_json.parent.mkdir(exist_ok=True)
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(res, f, indent=2)
            print(f"Saved to {out_json}")
            for t in res["turns"][:5]:
                print(f"  [{t['start_ms']}ms - {t['end_ms']}ms] {t['speaker']}: {t['text'][:90]}")
        except Exception as e:
            print(f"FAILED {stem}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
