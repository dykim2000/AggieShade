# AggieShade

AggieShade is a shade-aware pedestrian navigation project for the Texas A&M campus.

## Milestone 1: campus routing vertical slice

The first milestone is a conventional walking-route demo:

- select two TAMU buildings in the Expo mobile app;
- request a route from the FastAPI backend;
- calculate the shortest path through the bundled campus pedestrian graph; and
- draw the returned path on the map with distance and ETA.

Routes follow a bundled pedestrian graph instead of straight building-to-building lines. Buildings are snapped to nearby walkway access points, and the backend runs Dijkstra's algorithm across connected footways, pedestrian paths, crossings, and steps.

## Milestone 2: shade data foundation

Step 2 begins with a repeatable importer for Texas A&M's public tree inventory and university-building footprints. The importer:

- queries only the campus bounds used by the current routing graph;
- follows ArcGIS pagination so large tree layers are not truncated;
- preserves WGS 84 source geometry and adds local metric coordinates in UTM zone 14N (`EPSG:32614`);
- converts tree height and canopy spread from assumed feet to meters;
- estimates building height as floor count times 3.5 meters; and
- records provenance, assumptions, readiness totals, and per-feature quality flags.

The public tree layer does not declare measurement units in its service metadata. The feet-to-meters conversion is therefore an explicit, reviewable assumption rather than a claim about the source schema. Features with missing dimensions, removal dates, invalid geometry, or missing floor counts remain in the snapshot but are marked as unavailable for shade modeling.

To refresh the bundled shade inputs from the live TAMU service:

```bash
cd backend
python3 scripts/ingest_tamu_gis.py app/data/shade_features.json
```

The generated file is self-describing. Its `summary` object reports how many trees and buildings are ready for the next solar-shadow phase and why excluded records were rejected.

### Solar position service

The backend calculates solar altitude and azimuth for Texas A&M using NOAA's published approximate solar equations. Requests require a timezone-aware timestamp, are normalized to UTC, and include the start of the corresponding 15-minute cache bucket:

```bash
curl --get 'http://127.0.0.1:8000/shade/solar-position' \
  --data-urlencode 'at=2026-06-21T13:00:00-05:00'
```

The response distinguishes geometric altitude from atmosphere-adjusted apparent altitude. Azimuth is degrees clockwise from true north; `shadow_azimuth_degrees` points in the opposite direction. At night, `daylight` is false and the shadow direction is `null`.

The approximation is intentionally constrained to years 1800-2100 and has been checked against NOAA calculator results for College Station. It is suitable for the project's 15-minute shade buckets; field validation will determine whether a higher-precision solar model is warranted.

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
