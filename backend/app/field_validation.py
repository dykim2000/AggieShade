from __future__ import annotations

from datetime import datetime
from typing import Any


OBSERVATION_TYPES = {"shadow", "route"}
OBJECT_TYPES = {"tree", "building"}
ROUTE_PREFERENCES = {"fastest", "shadiest"}
CLOUD_CONDITIONS = {"clear", "partly_cloudy", "overcast"}


def _required(mapping: dict[str, Any], key: str, path: str) -> Any:
    if key not in mapping:
        raise ValueError(f"{path}.{key} is required")
    return mapping[key]


def _number(value: Any, path: str, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be a number")
    result = float(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{path} must be at least {minimum}")
    if maximum is not None and result > maximum:
        raise ValueError(f"{path} must be at most {maximum}")
    return result


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value.strip()


def _fraction(mapping: dict[str, Any], key: str, path: str) -> None:
    _number(_required(mapping, key, path), f"{path}.{key}", 0, 1)


def validate_field_observation(observation: dict[str, Any]) -> None:
    observation_id = _text(_required(observation, "observation_id", "observation"), "observation.observation_id")
    path = f"observation[{observation_id}]"

    observed_at = _text(_required(observation, "observed_at", path), f"{path}.observed_at")
    try:
        parsed_time = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{path}.observed_at must be ISO 8601") from exc
    if parsed_time.utcoffset() is None:
        raise ValueError(f"{path}.observed_at must include a timezone offset")

    observation_type = _text(
        _required(observation, "observation_type", path), f"{path}.observation_type"
    )
    if observation_type not in OBSERVATION_TYPES:
        raise ValueError(f"{path}.observation_type must be one of {sorted(OBSERVATION_TYPES)}")

    location = _required(observation, "location", path)
    if not isinstance(location, dict):
        raise ValueError(f"{path}.location must be an object")
    _number(_required(location, "latitude", f"{path}.location"), f"{path}.location.latitude", -90, 90)
    _number(_required(location, "longitude", f"{path}.location"), f"{path}.location.longitude", -180, 180)
    _number(
        _required(location, "gps_accuracy_m", f"{path}.location"),
        f"{path}.location.gps_accuracy_m",
        0,
    )

    conditions = _required(observation, "conditions", path)
    if not isinstance(conditions, dict):
        raise ValueError(f"{path}.conditions must be an object")
    cloud_condition = _text(
        _required(conditions, "cloud_condition", f"{path}.conditions"),
        f"{path}.conditions.cloud_condition",
    )
    if cloud_condition not in CLOUD_CONDITIONS:
        raise ValueError(f"{path}.conditions.cloud_condition must be one of {sorted(CLOUD_CONDITIONS)}")

    evidence = _required(observation, "evidence", path)
    if not isinstance(evidence, dict):
        raise ValueError(f"{path}.evidence must be an object")
    photos = _required(evidence, "photo_files", f"{path}.evidence")
    if not isinstance(photos, list) or not photos or any(not isinstance(photo, str) or not photo for photo in photos):
        raise ValueError(f"{path}.evidence.photo_files must contain at least one filename")

    if observation_type == "shadow":
        _validate_shadow_observation(observation, path)
    else:
        _validate_route_observation(observation, path)


def _validate_shadow_observation(observation: dict[str, Any], path: str) -> None:
    subject = _required(observation, "subject", path)
    if not isinstance(subject, dict):
        raise ValueError(f"{path}.subject must be an object")
    object_type = _text(_required(subject, "object_type", f"{path}.subject"), f"{path}.subject.object_type")
    if object_type not in OBJECT_TYPES:
        raise ValueError(f"{path}.subject.object_type must be one of {sorted(OBJECT_TYPES)}")
    _text(_required(subject, "source_feature_id", f"{path}.subject"), f"{path}.subject.source_feature_id")

    for measurement_name in ("observed", "predicted"):
        measurement = _required(observation, measurement_name, path)
        if not isinstance(measurement, dict):
            raise ValueError(f"{path}.{measurement_name} must be an object")
        _number(
            _required(measurement, "shadow_bearing_degrees", f"{path}.{measurement_name}"),
            f"{path}.{measurement_name}.shadow_bearing_degrees",
            0,
            360,
        )
        _number(
            _required(measurement, "shadow_length_m", f"{path}.{measurement_name}"),
            f"{path}.{measurement_name}.shadow_length_m",
            0,
        )
        _fraction(measurement, "walkway_shade_fraction", f"{path}.{measurement_name}")


def _validate_route_observation(observation: dict[str, Any], path: str) -> None:
    route = _required(observation, "route", path)
    if not isinstance(route, dict):
        raise ValueError(f"{path}.route must be an object")
    _text(_required(route, "origin_id", f"{path}.route"), f"{path}.route.origin_id")
    _text(_required(route, "destination_id", f"{path}.route"), f"{path}.route.destination_id")
    preference = _text(_required(route, "preference", f"{path}.route"), f"{path}.route.preference")
    if preference not in ROUTE_PREFERENCES:
        raise ValueError(f"{path}.route.preference must be one of {sorted(ROUTE_PREFERENCES)}")

    for measurement_name in ("observed", "predicted"):
        measurement = _required(observation, measurement_name, path)
        if not isinstance(measurement, dict):
            raise ValueError(f"{path}.{measurement_name} must be an object")
        _number(
            _required(measurement, "distance_m", f"{path}.{measurement_name}"),
            f"{path}.{measurement_name}.distance_m",
            0,
        )
        _number(
            _required(measurement, "duration_seconds", f"{path}.{measurement_name}"),
            f"{path}.{measurement_name}.duration_seconds",
            0,
        )
        _fraction(measurement, "shade_fraction", f"{path}.{measurement_name}")


def validate_field_dataset(dataset: dict[str, Any]) -> None:
    if dataset.get("schema_version") != "1.0":
        raise ValueError("schema_version must be '1.0'")
    observations = dataset.get("observations")
    if not isinstance(observations, list):
        raise ValueError("observations must be an array")

    seen_ids: set[str] = set()
    for observation in observations:
        if not isinstance(observation, dict):
            raise ValueError("each observation must be an object")
        validate_field_observation(observation)
        observation_id = observation["observation_id"]
        if observation_id in seen_ids:
            raise ValueError(f"duplicate observation_id: {observation_id}")
        seen_ids.add(observation_id)
