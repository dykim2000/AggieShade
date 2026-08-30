"""Download normalized tree and building shade inputs from TAMU GIS.

Usage:
    python scripts/ingest_tamu_gis.py app/data/shade_features.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.gis.tamu import DEFAULT_CAMPUS_BBOX, download_shade_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        default=DEFAULT_CAMPUS_BBOX,
        help="WGS 84 campus query bounds",
    )
    args = parser.parse_args()

    dataset = download_shade_dataset(bbox=args.bbox)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dataset, separators=(",", ":")) + "\n", encoding="utf-8")

    summary = dataset["summary"]
    print(
        f"Wrote {summary['tree_count']} trees and {summary['building_count']} buildings "
        f"in {dataset['source']['target_metric_crs']} to {args.output}"
    )


if __name__ == "__main__":
    main()
