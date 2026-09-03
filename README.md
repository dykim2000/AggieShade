# AggieShade

AggieShade is a shade-aware pedestrian navigation project for the Texas A&M campus.

## Milestone 1: campus routing vertical slice

The first milestone is a conventional walking-route demo:

- search across all 114 named buildings in the bundled TAMU campus snapshot;
- select a starting point and destination in the Expo mobile app;
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

### Tree-shadow service

The tree-shadow model loads all 2,058 shade-ready trees in the bundled snapshot. Each canopy is modeled as a circle with its recorded metric radius, then extended opposite the sun as a capsule-shaped polygon. Shadow length is `tree height / tan(apparent solar altitude)` and is capped at 100 meters near sunrise and sunset. Nighttime requests return an empty shadow list.

Geometry is generated and cached at 15-minute boundaries in UTM zone 14N (`EPSG:32614`). Request a bucket with a timezone-aware timestamp:

```bash
curl --get 'http://127.0.0.1:8000/shade/tree-shadows' \
  --data-urlencode 'at=2026-06-21T13:07:00-05:00'
```

The response reports the bucket time, solar direction, data-quality counts, cap metadata, and one closed metric polygon per eligible tree. The current capsule model intentionally favors fast campus-wide scoring; later field validation can replace it without changing the API's metric-coordinate contract.

The Expo map also requests `/shade/tree-shadows/map` after its initial interactions settle. That endpoint returns simplified WGS 84 polygons as one GeoJSON multipolygon, allowing the app to display the current bucket without recalculating the full metric response or rerendering the overlay when a search field receives focus. The overlay refreshes every 15 minutes and reports nighttime or connection status directly on the map.

### Building-shadow service (Week 9)

The building-shadow model uses the 109 shade-ready campus buildings in the bundled snapshot; 62 additional records are retained for provenance but excluded because they do not have a floor count. Eligible building heights are estimated as `floor_count * 3.5 meters`, matching the documented ingestion assumption.

For each building, the service sweeps the exact metric footprint opposite the sun instead of approximating it with a bounding box or convex hull. This preserves concave outlines, courtyard holes, and multipart buildings while extending the roof footprint by `building height / tan(apparent solar altitude)`. Like tree shadows, building geometry is generated and cached in 15-minute buckets, and shadow lengths are capped at 100 meters near sunrise and sunset. Nighttime requests return an empty shadow list.

Request the full UTM zone 14N (`EPSG:32614`) metric geometry for analysis and future pedestrian-edge scoring:

```bash
curl --get 'http://127.0.0.1:8000/shade/building-shadows' \
  --data-urlencode 'at=2026-06-21T13:07:00-05:00'
```

Request the corresponding WGS 84 GeoJSON prepared for the mobile map:

```bash
curl --get 'http://127.0.0.1:8000/shade/building-shadows/map' \
  --data-urlencode 'at=2026-06-21T13:07:00-05:00'
```

The Expo app consumes the map endpoint and renders live building shadows with the tree-shadow overlay. Both layers change direction and length with the current solar bucket and disappear at night.

### Shade-aware pedestrian routing

The route service projects all 2,535 pedestrian edges into the same UTM zone 14N coordinate system as the shadow models. For each 15-minute bucket, it dissolves overlapping tree and building shadows, measures the unique shaded fraction of every walkway, and caches those edge scores. This prevents overlapping tree canopies or building shadows from being counted twice.

The mobile app offers two preferences:

- **Fastest** minimizes physical walking distance while still reporting estimated shade coverage.
- **Shadiest** discounts the routing cost of each shaded meter by 70%, balancing additional shade against walking distance while keeping every edge cost positive.

Request a time-aware route with:

```bash
curl 'http://127.0.0.1:8000/routes' \
  --header 'Content-Type: application/json' \
  --data '{
    "origin_id": "zachry",
    "destination_id": "msc",
    "preference": "shadiest",
    "at": "2026-06-21T13:07:00-05:00"
  }'
```

The response includes physical distance, ETA, shaded distance, shade percentage, daylight status, the normalized shade-bucket time, and route geometry. At night, both preferences intentionally return the same shortest path with 0% modeled solar shade. Fastest and shadiest routes may also be identical when no useful shaded alternative exists. Trees and buildings excluded by the source-data quality rules are conservatively treated as unshaded, so coverage remains an estimate pending field validation.

The mobile app can also use a one-time foreground location as the route origin. Permission is
requested only after the user taps **My Location**. Coordinate origins are snapped to the connected
pedestrian graph and must be within 500 meters of it; destinations remain named campus buildings.
The route API accepts `origin: {"latitude": ..., "longitude": ...}` instead of `origin_id` for
this case. Exactly one origin form must be provided.

### Field validation

The [`field_validation`](field_validation) collection kit records real shadow and route
measurements beside the model predictions. It includes a blank session dataset, valid examples,
collection instructions, and a validator for timestamps, coordinates, measurements, evidence,
and observation IDs. From `backend`, validate a session with:

```bash
./.venv/bin/python scripts/validate_field_observations.py ../field_validation/observations.json
```

Store referenced photos in `field_validation/photos/`; that directory is intentionally ignored
to prevent large or privacy-sensitive field media from entering Git history.

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
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API is available at `http://127.0.0.1:8000`, with interactive docs at `/docs`.
For reliable physical-phone testing, use `--reload` only when the repository and virtual
environment are stored locally, as in the included VS Code task. In a cloud-synced folder, file
hydration can look like repeated source changes and trap Uvicorn in a reload loop. Keep generated
environments such as `.venv` and `mobile/node_modules` on local storage as well; cloud-offloaded
dependency files can make Python or Expo stall during startup.

## Run the mobile app

```bash
cd mobile
pnpm install
pnpm start
```

When using VS Code, press `Cmd+Shift+B` on macOS (`Ctrl+Shift+B` on Windows or
Linux) to run the default `AggieShade: Start App` task. It starts Uvicorn and
Expo in separate VS Code integrated terminals. Keep both tasks running while
testing on a phone, and terminate both tasks when you are finished.

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
