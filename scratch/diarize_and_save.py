import sys
import asyncio
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq()

def diarize_segments_with_llm(segments: list[dict]) -> list[dict]:
    """
    Classify each segment's speaker using Groq's fast LLM, then merge
    consecutive segments by the same speaker into cohesive turns.
    """
    total = len(segments)
    speaker_map = {}
    chunk_size = 60

    print(f"Diarizing {total} segments in chunks of {chunk_size}...")

    for i in range(0, total, chunk_size):
        chunk = segments[i:i + chunk_size]
        lines = [f"{i + idx}: {seg['text'].strip()}" for idx, seg in enumerate(chunk)]

        prompt = (
            "You are an expert audio diarization assistant for an Australian outbound internet sales call.\n"
            "The two speakers are:\n"
            "- 'Customer': Helen (answering the phone, giving details)\n"
            "- 'Agent': Marco Santos (introducing Internet's Comparison, explaining Dodo NBN plans, reading T&Cs and disclosures)\n\n"
            "For each line number below, assign 'Agent' or 'Customer'. Output JSON only mapping string line index to speaker.\n\n"
            "Lines:\n" + "\n".join(lines)
        )

        try:
            res = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="openai/gpt-oss-120b",
                response_format={"type": "json_object"},
                temperature=0.0
            )
            raw = res.choices[0].message.content
            parsed = json.loads(raw)
            for k, v in parsed.items():
                speaker_map[int(k)] = "Agent" if "agent" in str(v).lower() else "Customer"
        except Exception as e:
            print(f"LLM diarization chunk error: {e}")
            # Fallback heuristic for this chunk
            for idx, seg in enumerate(chunk):
                line_no = i + idx
                txt = seg['text'].lower()
                if any(w in txt for w in ["marco", "internet", "dodo", "comparison", "advise", "recorded", "plan", "nbn", "router", "modem", "terms"]):
                    speaker_map[line_no] = "Agent"
                elif any(w in txt for w in ["helen speaking", "good thanks", "yes", "yeah", "correct", "yep", "okay", "iprimus", "tpg"]):
                    speaker_map[line_no] = "Customer"
                else:
                    speaker_map[line_no] = "Agent" if (line_no % 2 == 1) else "Customer"

    # Now group consecutive segments with same speaker
    turns = []
    current_speaker = None
    current_texts = []
    current_start = None
    current_end = None
    turn_idx = 0

    for idx, seg in enumerate(segments):
        spk = speaker_map.get(idx, "Agent")
        seg_start = seg.get("start", 0.0)
        seg_end = seg.get("end", seg_start)
        seg_text = seg.get("text", "").strip()

        if not seg_text:
            continue

        if current_speaker is not None and spk != current_speaker:
            turns.append({
                "turn_index": turn_idx,
                "speaker": current_speaker,
                "text": " ".join(current_texts).strip(),
                "start_ms": int(current_start * 1000),
                "end_ms": int(current_end * 1000),
            })
            turn_idx += 1
            current_texts = []
            current_start = None

        current_speaker = spk
        if current_start is None:
            current_start = seg_start
        current_end = seg_end
        current_texts.append(seg_text)

    if current_texts and current_speaker is not None:
        turns.append({
            "turn_index": turn_idx,
            "speaker": current_speaker,
            "text": " ".join(current_texts).strip(),
            "start_ms": int(current_start * 1000),
            "end_ms": int(current_end * 1000),
        })

    return turns

def main():
    audio_path = Path("audio/3613793.mp3.mpeg")
    with open(audio_path, "rb") as f:
        tr = client.audio.transcriptions.create(
            file=("3613793.mp3", f),
            model="whisper-large-v3",
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )
    segments = getattr(tr, "segments", []) or []
    seg_list = []
    for s in segments:
        if isinstance(s, dict):
            seg_list.append({"start": s.get("start", 0), "end": s.get("end", 0), "text": s.get("text", "")})
        else:
            seg_list.append({"start": getattr(s, "start", 0), "end": getattr(s, "end", 0), "text": getattr(s, "text", "")})

    turns = diarize_segments_with_llm(seg_list)
    print(f"Total structured turns generated: {len(turns)}")

    full_text = getattr(tr, "text", "")
    duration_sec = float(getattr(tr, "duration", 0) or 0)

    result = {
        "turns": turns,
        "full_text": full_text,
        "duration_sec": duration_sec,
        "language": "en"
    }

    # Save to data/ for both leads (Option D fallback storage)
    for stem in ["3613793", "3613794"]:
        out = Path(f"data/transcript_{stem}.json")
        out.parent.mkdir(exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"Saved {out}")

    print("\nFirst 10 turns sample:")
    for t in turns[:10]:
        print(f"Turn {t['turn_index']} [{t['start_ms']}ms - {t['end_ms']}ms] {t['speaker']}: {t['text']}")

if __name__ == "__main__":
    main()
