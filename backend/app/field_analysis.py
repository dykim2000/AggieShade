from __future__ import annotations

from statistics import fmean
from typing import Any

from .field_validation import validate_field_dataset


def bearing_error_degrees(observed: float, predicted: float) -> float:
    difference = abs(observed - predicted) % 360
    return min(difference, 360 - difference)


def percent_error(observed: float, predicted: float) -> float | None:
    if observed == 0:
        return None
    return abs(predicted - observed) / observed * 100


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return round(fmean(values), 3) if values else None


def analyze_field_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    validate_field_dataset(dataset)
    shadow_results: list[dict[str, Any]] = []
    route_results: list[dict[str, Any]] = []

    for observation in dataset["observations"]:
        observed = observation["observed"]
        predicted = observation["predicted"]
        if observation["observation_type"] == "shadow":
            shadow_results.append(
                {
                    "observation_id": observation["observation_id"],
                    "object_type": observation["subject"]["object_type"],
                    "bearing_error_degrees": round(
                        bearing_error_degrees(
                            observed["shadow_bearing_degrees"],
                            predicted["shadow_bearing_degrees"],
                        ),
                        3,
                    ),
                    "length_error_m": round(
                        abs(predicted["shadow_length_m"] - observed["shadow_length_m"]), 3
                    ),
                    "length_error_percent": _rounded_percent_error(
                        observed["shadow_length_m"], predicted["shadow_length_m"]
                    ),
                    "walkway_shade_error_percentage_points": round(
                        abs(
                            predicted["walkway_shade_fraction"]
                            - observed["walkway_shade_fraction"]
                        )
                        * 100,
                        3,
                    ),
                }
            )
        else:
            route_results.append(
                {
                    "observation_id": observation["observation_id"],
                    "preference": observation["route"]["preference"],
                    "distance_error_m": round(
                        abs(predicted["distance_m"] - observed["distance_m"]), 3
                    ),
                    "distance_error_percent": _rounded_percent_error(
                        observed["distance_m"], predicted["distance_m"]
                    ),
                    "duration_error_seconds": round(
                        abs(predicted["duration_seconds"] - observed["duration_seconds"]), 3
                    ),
                    "duration_error_percent": _rounded_percent_error(
                        observed["duration_seconds"], predicted["duration_seconds"]
                    ),
                    "shade_error_percentage_points": round(
                        abs(predicted["shade_fraction"] - observed["shade_fraction"]) * 100,
                        3,
                    ),
                }
            )

    return {
        "schema_version": "1.0",
        "observation_count": len(dataset["observations"]),
        "shadow_summary": {
            "count": len(shadow_results),
            "mean_absolute_bearing_error_degrees": _mean(shadow_results, "bearing_error_degrees"),
            "mean_absolute_length_error_m": _mean(shadow_results, "length_error_m"),
            "mean_absolute_length_error_percent": _mean(shadow_results, "length_error_percent"),
            "mean_absolute_walkway_shade_error_percentage_points": _mean(
                shadow_results, "walkway_shade_error_percentage_points"
            ),
        },
        "route_summary": {
            "count": len(route_results),
            "mean_absolute_distance_error_m": _mean(route_results, "distance_error_m"),
            "mean_absolute_distance_error_percent": _mean(route_results, "distance_error_percent"),
            "mean_absolute_duration_error_seconds": _mean(route_results, "duration_error_seconds"),
            "mean_absolute_duration_error_percent": _mean(route_results, "duration_error_percent"),
            "mean_absolute_shade_error_percentage_points": _mean(
                route_results, "shade_error_percentage_points"
            ),
        },
        "shadow_observations": shadow_results,
        "route_observations": route_results,
    }


def _rounded_percent_error(observed: float, predicted: float) -> float | None:
    result = percent_error(observed, predicted)
    return round(result, 3) if result is not None else None
