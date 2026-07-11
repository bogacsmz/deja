import asyncio, sys
from dotenv import load_dotenv; load_dotenv(".env", override=False)
from deja.trigger import judge
s=sys.argv[1]
d=asyncio.run(judge(s))
print(f"  {'ACT ' if d.should_recall else 'skip'} {s[:42]:<42} -> {d.query!r}")
