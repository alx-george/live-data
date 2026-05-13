# live-data

Static data repository for live tracking projects. Updated automatically via GitHub Actions.
Served via GitHub Pages — no build pipeline, just raw file hosting.

## Endpoints

| File | Updated | URL |
|------|---------|-----|
| `bcferries/positions.json` | Every 15 min | `https://alx-george.github.io/live-data/bcferries/positions.json` |

## Structure

```
live-data/
├── bcferries/
│   └── positions.json        # AIS vessel positions (auto-updated)
├── fetch_ais.py              # BC Ferries AIS fetcher
├── requirements.txt
└── .github/
    └── workflows/
        └── fetch-bcferries.yml   # Cron: every 15 min
```

## positions.json schema

```json
{
  "updated_at": "2025-05-01T12:00:00+00:00",
  "vessel_count": 14,
  "vessels": [
    {
      "mmsi": 316001649,
      "name": "Spirit Of British Columbia",
      "lat": 48.9231,
      "lon": -123.4102,
      "sog": 18.4,
      "cog": 214.0,
      "heading": 216,
      "nav_status": "Under way using engine",
      "timestamp": "2025-05-01T11:58:32+00:00"
    }
  ]
}
```

## Setup

1. Add `AIS_API_KEY` secret in repo Settings → Secrets and variables → Actions
2. Enable GitHub Pages: Settings → Pages → Source: Deploy from branch → `main` / `(root)`
3. Trigger the workflow manually once to verify: Actions → Fetch BC Ferries AIS Positions → Run workflow

## Keeping the workflow alive

GitHub disables scheduled workflows after ~60 days of repo inactivity.
Run the workflow manually once a month, or set up a UptimeRobot monitor
to hit the GitHub API dispatch endpoint periodically.

## Adding BC Transit (future)

```
live-data/
├── bctransit/
│   └── vehicles.json
├── fetch_transit.py
└── .github/workflows/fetch-bctransit.yml
```
