"""
test_aisstream.py
-----------------
Minimal test — deploy to Render as a one-off job.
If vessels appear in the output, Render IPs are not blocked.
If vessel_count stays 0, Render IPs are blocked just like GitHub Actions.

Deploy steps:
1. Push this file + requirements.txt to a GitHub repo
2. Render dashboard → New → Background Worker → connect repo
3. Set environment variable: AIS_API_KEY = your key
4. Start command: python test_aisstream.py
5. Watch the logs
"""

import asyncio
import json
import os
import sys
import websockets
from datetime import datetime, timezone

AIS_WS_URL = "wss://stream.aisstream.io/v0/stream"
LISTEN_SECONDS = 60  # short test — 1 minute is enough to know

BCF_MMSIS = [
    316001649, 316001650, 316017849, 316017850, 316017848,
    316001653, 316001655, 316001656, 316001660, 316001661,
    316022501, 316022502, 316022503, 316022504, 316022505,
    316024001, 316024002, 316024003, 316024004,
    316014601, 316001690, 316001651, 316001654,
]

async def test():
    api_key = os.environ.get("AIS_API_KEY", "").strip()
    if not api_key:
        print("ERROR: AIS_API_KEY not set")
        sys.exit(1)

    subscribe_msg = {
        "APIkey": api_key,
        "BoundingBoxes": [[[47.5, -133.0], [55.5, -122.0]]],
        "FiltersShipMMSI": [str(m) for m in BCF_MMSIS],
        "FilterMessageTypes": ["PositionReport"],
    }

    vessel_count = 0
    print(f"[{datetime.now(timezone.utc).isoformat()}] Connecting...")

    try:
        async with websockets.connect(AIS_WS_URL, ping_interval=20) as ws:
            await ws.send(json.dumps(subscribe_msg))
            print(f"[{datetime.now(timezone.utc).isoformat()}] Subscribed. Listening {LISTEN_SECONDS}s...")

            deadline = asyncio.get_event_loop().time() + LISTEN_SECONDS
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    msg = json.loads(raw)
                    meta = msg.get("MetaData", {})
                    mmsi = meta.get("MMSI")
                    name = meta.get("ShipName", "").strip()
                    lat  = meta.get("latitude")
                    lon  = meta.get("longitude")
                    if mmsi:
                        vessel_count += 1
                        print(f"  VESSEL: {name or mmsi}  lat={lat}  lon={lon}")
                except asyncio.TimeoutError:
                    print("  (no message in 10s, still waiting...)")

    except Exception as e:
        print(f"ERROR: {e}")

    print(f"\n--- RESULT ---")
    print(f"vessel_count : {vessel_count}")
    print(f"verdict      : {'RENDER IPs NOT BLOCKED - proceed with proxy' if vessel_count > 0 else 'RENDER IPs BLOCKED - same as GitHub Actions'}")

if __name__ == "__main__":
    asyncio.run(test())
