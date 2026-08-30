# AggieShade

AggieShade is a shade-aware pedestrian navigation project for the Texas A&M campus.

## Milestone 1: campus routing vertical slice

The first milestone is a conventional walking-route demo:

- select two TAMU buildings in the Expo mobile app;
- request a route from the FastAPI backend;
- calculate the shortest path through a small campus walkway graph; and
- draw the returned path on the map with distance and ETA.

The embedded graph is intentionally small. It proves the app-to-API-to-map flow before the later TAMU GIS ingestion and shade-scoring milestones.

## Run the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0
```

The API is available at `http://127.0.0.1:8000`, with interactive docs at `/docs`.

## Run the mobile app

```bash
cd mobile
pnpm install
pnpm start
```

The default API URL is `http://127.0.0.1:8000`. For a physical phone, create `mobile/.env` and point it at the computer's LAN address:

```text
EXPO_PUBLIC_API_URL=http://192.168.x.x:8000
```

## Verify

```bash
cd backend
python3 -m unittest discover -s tests -v

cd ../mobile
pnpm typecheck
```
