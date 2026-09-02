#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.field_analysis import analyze_field_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze AggieShade field-observation errors.")
    parser.add_argument("dataset", type=Path, help="Validated observation JSON")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()

    try:
        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
        if not isinstance(dataset, dict):
            raise ValueError("dataset root must be an object")
        report = analyze_field_dataset(dataset)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Could not analyze field dataset: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote analysis for {report['observation_count']} observation(s) to {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
