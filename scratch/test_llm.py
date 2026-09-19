import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from services.openrouter import get_openrouter_client

async def test():
    client = get_openrouter_client()
    print("OpenRouter client configured:", client.is_configured, "Model:", client.model)
    try:
        res = await asyncio.wait_for(client.complete_json('Answer with JSON: {"status": "ok"}'), timeout=10)
        print("OpenRouter test response:", res)
    except Exception as e:
        print("OpenRouter test error:", type(e), e)

asyncio.run(test())
