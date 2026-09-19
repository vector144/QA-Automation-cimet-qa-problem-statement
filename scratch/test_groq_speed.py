import time
import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq()

t0 = time.time()
res = client.chat.completions.create(
    messages=[{"role": "user", "content": 'Is the sentence "This call may be recorded for quality purposes" a call recording disclaimer? Reply in JSON: {"status": "PASS" or "FAIL"}'}],
    model="openai/gpt-oss-120b",
    response_format={"type": "json_object"},
    temperature=0.0
)
print("Groq Latency:", round(time.time() - t0, 2), "seconds")
print("Response:", res.choices[0].message.content)
