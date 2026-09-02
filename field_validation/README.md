# AggieShade field-validation collection kit

Use this folder to record real campus conditions alongside AggieShade predictions. Keep one
copy of `observations.json` for a collection session and store referenced photos outside Git.
The example file demonstrates both supported observation types; its values are illustrative.

## Before collecting

- Use a phone with location services and automatic date/time enabled.
- Record only when a tree or building casts a visible shadow. Mark overcast observations as
  `overcast`; do not invent a shadow edge.
- Avoid photographing identifiable people. Do not stand in streets, bike lanes, construction
  areas, or other unsafe locations to improve a measurement.
- Use stable source feature IDs from AggieShade wherever possible.

## Shadow observation

1. Open AggieShade and note the prediction at the exact observation time.
2. Stand at the tree trunk or the relevant building edge and record GPS coordinates and the
   phone's reported accuracy.
3. Measure shadow bearing clockwise from true north and shadow length in meters. For irregular
   shadows, use the centerline and furthest representative edge rather than a single outlier.
4. Estimate the fraction of the nearby walkway covered by the shadow from `0` to `1`.
5. Take at least one photo showing both the object base and shadow direction.

## Route observation

1. Record the selected origin, destination, preference, predicted distance, duration, and shade.
2. Walk the suggested route without intentional detours and record actual duration and distance.
3. At regular intervals, classify the walked segment as sunny, partial, or shaded. Convert the
   accumulated shaded distance to a fraction from `0` to `1`.
4. Reference at least one start photo; additional photos should share the observation filename
   prefix. Note any construction, clouds, or inaccessible segments.

Collect a balanced sample in morning, solar midday, and late afternoon, including open paths,
dense tree cover, short and tall buildings, and both route preferences. Repeat a subset on another
day to distinguish model error from measurement noise.

## Validate a session

From `backend`, run:

```bash
./.venv/bin/python scripts/validate_field_observations.py ../field_validation/observations.json
```

The validator rejects missing timezone offsets, invalid coordinates, out-of-range fractions,
unsupported categories, missing evidence filenames, incomplete type-specific measurements, and
duplicate observation IDs.
