"""Validation of normalized public records."""

from __future__ import annotations

import re
from typing import Any

from canawler.dataset import CANAL_MILES
from canawler.reference import ReferenceDataError


def _unique_ids(
    records: list[dict[str, Any]], label: str, *, url_safe: bool = True
) -> set[str]:
    ids = [record.get("id") for record in records]
    if any(
        not isinstance(value, str)
        or not value
        or (url_safe and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value) is None)
        for value in ids
    ):
        raise ReferenceDataError(f"{label}: IDs must be non-empty and URL-safe")
    if len(ids) != len(set(ids)):
        raise ReferenceDataError(f"{label}: IDs must be unique")
    return set(ids)


def _feature_fields(record: dict[str, Any], label: str) -> None:
    for field in ("name", "feature_type"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ReferenceDataError(f"{label}: {field} is required")
    mile = record.get("mile")
    if isinstance(mile, bool) or not isinstance(mile, (int, float)):
        raise ReferenceDataError(f"{label}: mile must be numeric")
    if not 0 <= mile <= CANAL_MILES:
        raise ReferenceDataError(f"{label}: mile is outside the canal")
    end = record.get("mile_end")
    if end is not None and not mile <= end <= CANAL_MILES:
        raise ReferenceDataError(f"{label}: mile_end is invalid")
    latitude = record.get("latitude")
    longitude = record.get("longitude")
    if not isinstance(latitude, (int, float)) or not -90 <= latitude <= 90:
        raise ReferenceDataError(f"{label}: latitude is invalid")
    if not isinstance(longitude, (int, float)) or not -180 <= longitude <= 180:
        raise ReferenceDataError(f"{label}: longitude is invalid")
    source_ids = record.get("source_ids")
    if not isinstance(source_ids, list) or not source_ids:
        raise ReferenceDataError(f"{label}: source_ids are required")


def validate_public_records(records: dict[str, Any], sources: dict[str, Any]) -> None:
    """Fail if referential, geographic, ordering, or uniqueness invariants fail."""
    source_ids = _unique_ids(sources["sources"], "sources", url_safe=False)
    feature_ids = _unique_ids(records["features"], "features")
    access_ids = _unique_ids(records["access_points"], "access points")
    lock_ids = _unique_ids(records["locks"], "locks")
    if not (access_ids | lock_ids) <= feature_ids:
        raise ReferenceDataError("dedicated access-point and lock IDs must be features")

    for index, record in enumerate(records["features"]):
        _feature_fields(record, f"feature {index}")
        unknown = set(record["source_ids"]) - source_ids
        if unknown:
            raise ReferenceDataError(
                f"feature {record['id']}: unknown sources {unknown}"
            )
    expected_order = sorted(
        records["features"],
        key=lambda item: (item["mile"], item["feature_type"], item["name"], item["id"]),
    )
    if records["features"] != expected_order:
        raise ReferenceDataError("features must be in deterministic canal order")

    for artifact, ids in sources["artifacts"].items():
        unknown = set(ids) - source_ids
        if unknown:
            raise ReferenceDataError(f"artifact {artifact}: unknown sources {unknown}")
    for relationship in records["relationships"]:
        if relationship["from_id"] not in access_ids:
            raise ReferenceDataError("relationship source must be an access point")
        if relationship["to_id"] not in feature_ids:
            raise ReferenceDataError("relationship target must be a feature")
        distance = relationship["mile_distance"]
        if not isinstance(distance, (int, float)) or not 0 <= distance <= 1:
            raise ReferenceDataError("relationship mile distance is invalid")


__all__ = ["validate_public_records"]
