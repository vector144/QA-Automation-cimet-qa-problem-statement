import json

d = json.load(open('data/transcript_3613793.json'))
print('Total turns:', len(d['turns']))
for t in d['turns']:
    txt = t['text'].lower()
    for k in ['recorded for quality', 'cooling off', '42', 'modem', 'dodo']:
        if k in txt:
            print(f"[{k.upper()}] Turn {t['turn_index']} ({t['start_ms']}ms / {t['start_ms']/1000:.1f}s): {t['speaker']} -> {t['text'][:90]}")
            break
