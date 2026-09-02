#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.field_validation import validate_field_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an AggieShade field-observation dataset.")
    parser.add_argument("dataset", type=Path, help="JSON dataset to validate")
    args = parser.parse_args()

    try:
        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
        if not isinstance(dataset, dict):
            raise ValueError("dataset root must be an object")
        validate_field_dataset(dataset)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Invalid field dataset: {exc}", file=sys.stderr)
        return 1

    print(f"Valid field dataset: {len(dataset['observations'])} observation(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
