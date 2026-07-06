import asyncio
import json
import os
from fbchat_muqit import Client

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cookies.json")


async def main():
    try:
        async with Client(cookies_file_path=PATH, disable_logs=True) as c:
            print("WHOAMI_OK " + json.dumps({"uid": c.uid, "name": c.name}))
            threads = list(await c.fetch_thread_list(limit=3))
            print("THREADS_OK count=%d" % len(threads))
            for t in threads:
                print(
                    "  thread:",
                    getattr(t, "id", "?"),
                    "|",
                    str(getattr(t, "name", ""))[:40],
                )
    except Exception as e:
        print("FB_ERR " + repr(e)[:400])


asyncio.run(main())
