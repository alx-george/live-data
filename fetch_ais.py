"""
fetch_ais.py
------------
Connects to aisstream.io WebSocket, subscribes to AIS messages for
BC Ferries vessels (by MMSI), listens for up to LISTEN_SECONDS,
then writes bcferries/positions.json.

Environment variables:
  AIS_API_KEY   — aisstream.io API key (required)

Output: bcferries/positions.json
  {
    "updated_at": "2025-05-01T12:00:00+00:00",
    "vessel_count": 14,
    "vessels": [
      {
        "mmsi": 316001649,
        "name": "Spirit of British Columbia",
        "lat": 48.9231,
        "lon": -123.4102,
        "sog": 18.4,
        "cog": 214.0,
        "heading": 216,
        "nav_status": "Under way using engine",
        "timestamp": "2025-05-01T11:58:32+00:00"
      },
      ...
    ]
  }
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import websockets

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

AIS_WS_URL     = "wss://stream.aisstream.io/v0/stream"
LISTEN_SECONDS = 480          # 8 minutes — enough to see most active vessels
OUTPUT_PATH    = Path("bcferries/positions.json")

# All verified BC Ferries MMSIs (from BC_Ferries_List_with_MMSI.xlsx)
BCF_MMSIS = [
    316001649, 316001650,  # Spirit class
    316017849, 316017850, 316017848,  # Coastal class
    316001653, 316001655, 316001656, 316001660, 316001661,  # Super / Queen class
    316022501, 316022502, 316022503, 316022504, 316022505,  # Island class
    316024001, 316024002, 316024003, 316024004,  # Salish class
    316014601, 316001690,  # Northern Expedition / Adventure
    316001651, 316001654, 316001658, 316001659,  # Queen / Bowen / Mayne class
    316001662, 316001663, 316001664, 316001665,  # Quinitsa / Kahloke / Howe Sound / Stikine
    316001666, 316001667, 316001668, 316001669,  # Kuper / Kahloke / Dogwood / Howe Sound Princess
    316001652, 316001657,  # Reserve MMSIs — include in case fleet list updates
]

# Human-readable nav status codes
NAV_STATUS = {
    0: "Under way using engine",
    1: "At anchor",
    2: "Not under command",
    3: "Restricted manoeuvrability",
    4: "Constrained by draught",
    5: "Moored",
    6: "Aground",
    7: "Engaged in fishing",
    8: "Under way sailing",
    15: "Not defined",
}

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

async def fetch():
    api_key = os.environ.get("AIS_API_KEY", "").strip()
    if not api_key:
        print("ERROR: AIS_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    # Subscribe message — filter to BCF bounding box + our MMSI list
    subscribe_msg = {
        "APIkey": api_key,
        "BoundingBoxes": [
            # Main BC coast + Haida Gwaii
            [[47.5, -133.0], [55.5, -122.0]]
        ],
        "FilterMessageTypes": ["PositionReport", "StandardClassBPositionReport"],
    }

    vessels: dict[int, dict] = {}   # mmsi -> latest data
    mmsi_set = set(BCF_MMSIS)

    print(f"Connecting to aisstream.io... (listening {LISTEN_SECONDS}s)")

    try:
        async with websockets.connect(
            AIS_WS_URL,
            extra_headers={"User-Agent": "bcferries-live-tracker/1.0"},
            ping_interval=20,
            ping_timeout=30,
            close_timeout=10,
        ) as ws:
            await ws.send(json.dumps(subscribe_msg))
            print("Subscribed. Waiting for position reports...")

            deadline = asyncio.get_event_loop().time() + LISTEN_SECONDS

            while asyncio.get_event_loop().time() < deadline:
                try:
                    remaining = deadline - asyncio.get_event_loop().time()
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(30, remaining))
                except asyncio.TimeoutError:
                    # No message for 30 s — aisstream may be quiet, keep waiting
                    continue

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("MessageType", "")
                if msg_type not in ("PositionReport", "StandardClassBPositionReport"):
                    continue

                meta  = msg.get("MetaData", {})
                mmsi  = int(meta.get("MMSI", 0))

                # Only keep BC Ferries vessels
                if mmsi not in mmsi_set:
                    continue

                body = msg.get("Message", {}).get(msg_type, {})

                lat = meta.get("latitude",  body.get("Latitude",  None))
                lon = meta.get("longitude", body.get("Longitude", None))

                if lat is None or lon is None:
                    continue

                # Filter out obviously invalid positions (0,0 or out of range)
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    continue
                if lat == 0.0 and lon == 0.0:
                    continue

                sog     = body.get("Sog",            None)   # speed over ground (knots)
                cog     = body.get("Cog",            None)   # course over ground (degrees)
                heading = body.get("TrueHeading",    None)   # true heading (degrees)
                nav_raw = body.get("NavigationalStatus", 15)
                name    = meta.get("ShipName", "").strip().title() or None

                # SOG / COG sanity — aisstream occasionally sends 102.3 for "not available"
                if sog is not None and sog > 102:
                    sog = None
                if cog is not None and cog > 360:
                    cog = None
                if heading is not None and heading > 360:
                    heading = None

                vessels[mmsi] = {
                    "mmsi":       mmsi,
                    "name":       name,
                    "lat":        round(lat, 6),
                    "lon":        round(lon, 6),
                    "sog":        round(sog, 1) if sog is not None else None,
                    "cog":        round(cog, 1) if cog is not None else None,
                    "heading":    int(heading) if heading is not None else None,
                    "nav_status": NAV_STATUS.get(nav_raw, "Unknown"),
                    "timestamp":  datetime.now(timezone.utc).isoformat(),
                }

                print(f"  [{len(vessels):>2} vessels] {mmsi} {name or '(unnamed)'} "
                      f"@ {lat:.4f},{lon:.4f}  SOG {sog} kts")

    except websockets.exceptions.ConnectionClosedError as e:
        print(f"WebSocket closed early: {e}", file=sys.stderr)
    except OSError as e:
        print(f"Connection error: {e}", file=sys.stderr)

    # -----------------------------------------------------------------------
    # Write output regardless — even if 0 vessels (keeps updated_at current)
    # -----------------------------------------------------------------------
    vessel_list = sorted(vessels.values(), key=lambda v: v["mmsi"])

    output = {
        "updated_at":    datetime.now(timezone.utc).isoformat(),
        "vessel_count":  len(vessel_list),
        "vessels":       vessel_list,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nWrote {len(vessel_list)} vessels to {OUTPUT_PATH}")
    print(f"updated_at: {output['updated_at']}")


if __name__ == "__main__":
    asyncio.run(fetch())
