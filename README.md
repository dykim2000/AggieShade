# AggieShade

AggieShade is a shade-aware pedestrian navigation project for the Texas A&M campus.

## Milestone 1: campus routing vertical slice

The first milestone is a conventional walking-route demo:

- select two TAMU buildings in the Expo mobile app;
- request a route from the FastAPI backend;
- calculate the shortest path through a small campus walkway graph; and
- draw the returned path on the map with distance and ETA.

Routes follow a bundled pedestrian graph instead of straight building-to-building lines. Buildings are snapped to nearby walkway access points, and the backend runs Dijkstra's algorithm across connected footways, pedestrian paths, crossings, and steps.

## Pedestrian routing data

The bundled graph in `backend/app/data/pedestrian_graph.json` is derived from [OpenStreetMap](https://www.openstreetmap.org/) data and is available under the [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) license. Texas A&M's [official sidewalk layer](https://gis.tamu.edu/arcgis/rest/services/FCOR/TAMU_BaseMap/MapServer/18) can be used for visual validation.

To refresh the graph:

```bash
curl 'https://api.openstreetmap.org/api/0.6/map?bbox=-96.346,30.609,-96.338,30.6225' -o campus.osm
cd backend
python3 scripts/build_pedestrian_graph.py ../campus.osm app/data/pedestrian_graph.json
```

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
