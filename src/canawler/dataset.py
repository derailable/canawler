"""Normalize curated C&O Canal references into a small public data model."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

from shapely.geometry import LineString

from canawler.geography import CANAL_MILES, milepoint_locator, point_at_mile
from canawler.reference import ReferenceDataError

SCHEMA_VERSION = 1
REFERENCE_DIR = Path("data/reference")

ACCESS_SOURCE_ID = "co_canal_association_access_points"
RECREATION_SOURCE_ID = "nps_recreation_guide"
NPS_LOCK_SOURCE_ID = "nps_lift_locks"
TRUST_LOCK_SOURCE_ID = "co_canal_trust_locks"
TOWPATH_SOURCE_ID = "nps_towpath_reference"

AMENITY_FIELDS = (
    "parking",
    "restrooms",
    "water",
    "picnic_tables",
    "camping",
    "camping_fee_area",
    "camping_tent",
    "boat_ramp",
    "canoe_kayak_ramp",
    "visitor_center",
    "food",
    "bike_rentals",
    "boat_rentals",
    "canal_quarters",
    "fee_area",
)


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReferenceDataError(f"could not read {path}: {error}") from error
    if not isinstance(value, dict):
        raise ReferenceDataError(f"{path}: root must be an object")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReferenceDataError(f"{label}: expected a number")
    return float(value)


def _source(source: Any, label: str) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise ReferenceDataError(f"{label}: source must be an object")
    if (
        not str(source.get("name", "")).strip()
        or not str(source.get("url", "")).strip()
    ):
        raise ReferenceDataError(f"{label}: source name and URL are required")
    return source


def _check_mile(value: Any, label: str) -> float:
    mile = _number(value, label)
    if not 0 <= mile <= CANAL_MILES:
        raise ReferenceDataError(f"{label}: must be between 0 and {CANAL_MILES}")
    return mile


def _check_coordinates(latitude: Any, longitude: Any, label: str) -> None:
    lat = _number(latitude, f"{label} latitude")
    lon = _number(longitude, f"{label} longitude")
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ReferenceDataError(f"{label}: coordinates are outside WGS84 bounds")


def load_access_points(path: Path | None = None) -> dict[str, Any]:
    path = path or REFERENCE_DIR / "access-points.json"
    data = _load_object(path)
    _source(data.get("source"), str(path))
    records = data.get("access_points")
    if not isinstance(records, list):
        raise ReferenceDataError(f"{path}: access_points must be an array")
    expected = {"name", "milepost", "milepost_end", "latitude", "longitude"}
    seen: set[tuple[Any, ...]] = set()
    previous: tuple[float, str] | None = None
    for index, record in enumerate(records):
        label = f"{path}: access point {index}"
        if not isinstance(record, dict) or set(record) != expected:
            raise ReferenceDataError(f"{label}: fields do not match the schema")
        if not isinstance(record["name"], str) or not record["name"].strip():
            raise ReferenceDataError(f"{label}: name is required")
        mile = _check_mile(record["milepost"], f"{label} milepost")
        end = record["milepost_end"]
        if end is not None and not mile <= _check_mile(end, f"{label} end"):
            raise ReferenceDataError(f"{label}: milepost_end precedes milepost")
        _check_coordinates(record["latitude"], record["longitude"], label)
        order = (mile, record["name"])
        if previous is not None and order < previous:
            raise ReferenceDataError(f"{path}: records must be sorted")
        previous = order
        signature = tuple(record[field] for field in sorted(expected))
        if signature in seen:
            raise ReferenceDataError(f"{label}: exact duplicate")
        seen.add(signature)
    return data


def load_locks(path: Path | None = None) -> dict[str, Any]:
    path = path or REFERENCE_DIR / "locks.json"
    data = _load_object(path)
    sources = data.get("sources")
    if not isinstance(sources, list) or len(sources) != 2:
        raise ReferenceDataError(f"{path}: expected two lock sources")
    for source in sources:
        _source(source, str(path))
    records = data.get("locks")
    if not isinstance(records, list) or len(records) != 74:
        raise ReferenceDataError(f"{path}: expected exactly 74 lift locks")
    seen: set[str] = set()
    previous: tuple[float, str] | None = None
    for index, record in enumerate(records):
        label = f"{path}: lock {index}"
        if not isinstance(record, dict):
            raise ReferenceDataError(f"{label}: must be an object")
        number = record.get("lock_number")
        name = record.get("name")
        if not isinstance(number, str) or not number.strip() or number in seen:
            raise ReferenceDataError(f"{label}: lock_number must be unique")
        if not isinstance(name, str) or not name.strip():
            raise ReferenceDataError(f"{label}: name is required")
        seen.add(number)
        mile = _check_mile(record.get("milepost"), f"{label} milepost")
        alternate = record.get("alternate_milepost")
        if alternate is not None:
            _check_mile(alternate, f"{label} alternate_milepost")
        order = (mile, number)
        if previous is not None and order < previous:
            raise ReferenceDataError(f"{path}: records must be sorted")
        previous = order
    if not {"1", "75", "63 1/3", "64 2/3"} <= seen or "65" in seen:
        raise ReferenceDataError(f"{path}: lock numbering invariants failed")
    return data


def load_recreation_guide(path: Path | None = None) -> dict[str, Any]:
    path = path or REFERENCE_DIR / "recreation-guide.json"
    data = _load_object(path)
    _source(data.get("source"), str(path))
    records = data.get("locations")
    if not isinstance(records, list):
        raise ReferenceDataError(f"{path}: locations must be an array")
    seen: set[tuple[Any, ...]] = set()
    previous: tuple[float, str] | None = None
    for index, record in enumerate(records):
        label = f"{path}: recreation location {index}"
        if not isinstance(record, dict):
            raise ReferenceDataError(f"{label}: must be an object")
        name = record.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ReferenceDataError(f"{label}: name is required")
        mile = _check_mile(record.get("milepost"), f"{label} milepost")
        amenities = record.get("amenities")
        if not isinstance(amenities, dict) or set(amenities) != set(AMENITY_FIELDS):
            raise ReferenceDataError(f"{label}: amenities do not match the schema")
        if any(not isinstance(amenities[field], bool) for field in AMENITY_FIELDS):
            raise ReferenceDataError(f"{label}: amenities must be booleans")
        if amenities["camping"] != (
            amenities["camping_fee_area"] or amenities["camping_tent"]
        ):
            raise ReferenceDataError(f"{label}: camping fields disagree")
        order = (mile, name)
        if previous is not None and order < previous:
            raise ReferenceDataError(f"{path}: records must be sorted")
        previous = order
        signature = (
            normalize_name(name),
            mile,
            *(amenities[f] for f in AMENITY_FIELDS),
        )
        if signature in seen:
            raise ReferenceDataError(f"{label}: normalized duplicate")
        seen.add(signature)
    return data


def normalize_name(value: str) -> str:
    value = value.casefold().replace("’", "'")
    value = re.sub(r"'s\b", "s", value)
    value = re.sub(r"\bno\.?\s+(?=\d)", "", value)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def _slug(value: Any) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", str(value))
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold()
    )
    return "-".join(re.findall(r"[a-z0-9]+", ascii_value))


def _mile_slug(value: Any) -> str:
    return _slug(str(value).replace("-", "minus-"))


def stable_ids(prefix: str, records: list[dict[str, Any]]) -> list[str]:
    """Create deterministic, URL-safe IDs independent of record ordering."""
    bases = [
        "-".join(
            part
            for part in (prefix, _slug(record["name"]), _mile_slug(record["milepost"]))
            if part
        )
        for record in records
    ]
    counts = Counter(bases)
    result = []
    for base, record in zip(bases, records, strict=True):
        if counts[base] == 1:
            result.append(base)
            continue
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
        result.append(f"{base}-{hashlib.sha256(canonical.encode()).hexdigest()[:8]}")
    if len(result) != len(set(result)) or any(
        re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value) is None for value in result
    ):
        raise ReferenceDataError(f"{prefix} IDs are not unique and URL-safe")
    return result


def names_match(left: str, right: str) -> bool:
    """Apply the sibling project's conservative access-point name matching rules."""
    left_name = normalize_name(left)
    right_name = normalize_name(right)
    kinds = ("aqueduct", "bridge", "dam", "lock", "tunnel")
    left_kind = next((word for word in kinds if word in left_name.split()), None)
    right_kind = next((word for word in kinds if word in right_name.split()), None)
    if left_kind and right_kind and left_kind != right_kind:
        return False
    if left_name == right_name or left_name in right_name or right_name in left_name:
        return True
    ignored = {"access", "boat", "center", "lock", "park", "state", "visitor"}
    left_tokens = {token for token in left_name.split() if token not in ignored}
    right_tokens = {token for token in right_name.split() if token not in ignored}
    return any(len(token) >= 5 for token in left_tokens & right_tokens)


def mile_distance(record: dict[str, Any], milepost: float) -> float:
    start = Decimal(str(record["milepost"]))
    end = Decimal(str(record.get("milepost_end") or record["milepost"]))
    feature = Decimal(str(milepost))
    if start <= feature <= end:
        return 0.0
    return float(min(abs(feature - start), abs(feature - end)))


def feature_type(name: str, amenities: dict[str, bool]) -> str:
    lowered = name.casefold()
    if "lockhouse" in lowered:
        return "lockhouse"
    if "lock" in lowered:
        return "lock"
    if "aqueduct" in lowered:
        return "aqueduct"
    if re.search(r"\bdam\b", lowered):
        return "dam"
    if "tunnel" in lowered:
        return "tunnel"
    if "bridge" in lowered:
        return "bridge"
    if "junction" in lowered:
        return "railroad_junction"
    if "station" in lowered:
        return "railroad_station"
    if amenities["visitor_center"] or "visitor center" in lowered:
        return "visitor_center"
    if amenities["canal_quarters"]:
        return "canal_quarters"
    if amenities["camping"]:
        return "campground"
    if amenities["boat_ramp"] or amenities["canoe_kayak_ramp"]:
        return "boat_access"
    if "fort " in lowered:
        return "historic_site"
    return "recreation_location"


def _lock_number(name: str) -> str | None:
    match = re.search(r"\block\s+(\d+(?:\s+\d+/\d+)?)\b", name, re.IGNORECASE)
    return match.group(1) if match else None


def build_records(geometry: LineString) -> dict[str, Any]:
    access_data = load_access_points()
    lock_data = load_locks()
    recreation_data = load_recreation_guide()
    access_input = access_data["access_points"]
    lock_input = lock_data["locks"]
    recreation_input = recreation_data["locations"]
    locate_mile = milepoint_locator(geometry)

    access_ids = stable_ids("access", access_input)
    lock_ids = [f"lock-{_slug(record['lock_number'])}" for record in lock_input]
    recreation_ids = stable_ids("nps", recreation_input)
    if len(lock_ids) != len(set(lock_ids)):
        raise ReferenceDataError("lock IDs are not unique")

    match_indexes: list[list[int]] = []
    for access in access_input:
        indexes = [
            index
            for index, location in enumerate(recreation_input)
            if mile_distance(access, location["milepost"]) <= 0.35
            and names_match(access["name"], location["name"])
        ]
        match_indexes.append(indexes)

    access_points = []
    for record, public_id, indexes in zip(
        access_input, access_ids, match_indexes, strict=True
    ):
        amenities = None if not indexes else {field: False for field in AMENITY_FIELDS}
        for index in indexes:
            for field in AMENITY_FIELDS:
                amenities[field] = (
                    amenities[field] or recreation_input[index]["amenities"][field]
                )
        source_ids = [ACCESS_SOURCE_ID]
        if indexes:
            source_ids.append(RECREATION_SOURCE_ID)
        access_points.append(
            {
                "id": public_id,
                "name": record["name"],
                "mile": record["milepost"],
                "mile_end": record["milepost_end"],
                "latitude": record["latitude"],
                "longitude": record["longitude"],
                "amenities": amenities,
                "source_ids": source_ids,
            }
        )

    locks = []
    for record, public_id in zip(lock_input, lock_ids, strict=True):
        latitude, longitude = locate_mile(record["milepost"])
        locks.append(
            {
                "id": public_id,
                "lock_number": record["lock_number"],
                "name": record["name"],
                "common_name": record["common_name"],
                "mile": record["milepost"],
                "alternate_mile": record["alternate_milepost"],
                "latitude": latitude,
                "longitude": longitude,
                "notes": record["notes"],
                "source_ids": [
                    NPS_LOCK_SOURCE_ID,
                    TRUST_LOCK_SOURCE_ID,
                    TOWPATH_SOURCE_ID,
                ],
            }
        )

    features = [
        {
            "id": record["id"],
            "name": record["name"],
            "feature_type": "access_point",
            "mile": record["mile"],
            "mile_end": record["mile_end"],
            "latitude": record["latitude"],
            "longitude": record["longitude"],
            "source_ids": record["source_ids"],
        }
        for record in access_points
    ]
    features.extend(
        {
            "id": record["id"],
            "name": record["name"],
            "feature_type": "lock",
            "mile": record["mile"],
            "mile_end": None,
            "latitude": record["latitude"],
            "longitude": record["longitude"],
            "source_ids": record["source_ids"],
        }
        for record in locks
    )

    lock_id_by_number = {
        record["lock_number"]: public_id
        for record, public_id in zip(lock_input, lock_ids, strict=True)
    }
    recreation_features: list[dict[str, Any]] = []
    for record, public_id in zip(recreation_input, recreation_ids, strict=True):
        if _lock_number(record["name"]) in lock_id_by_number:
            continue
        latitude, longitude = locate_mile(record["milepost"])
        item = {
            "id": public_id,
            "name": record["name"],
            "feature_type": feature_type(record["name"], record["amenities"]),
            "mile": record["milepost"],
            "mile_end": None,
            "latitude": latitude,
            "longitude": longitude,
            "source_ids": [RECREATION_SOURCE_ID, TOWPATH_SOURCE_ID],
        }
        recreation_features.append(item)
        features.append(item)

    features.sort(
        key=lambda item: (
            item["mile"],
            item["feature_type"],
            item["name"],
            item["id"],
        )
    )

    relationships = []
    for access, access_id, indexes in zip(
        access_input, access_ids, match_indexes, strict=True
    ):
        for index in indexes:
            source_lock_number = _lock_number(recreation_input[index]["name"])
            target_id = lock_id_by_number.get(source_lock_number, recreation_ids[index])
            relationships.append(
                {
                    "relationship_type": "source_match",
                    "from_id": access_id,
                    "to_id": target_id,
                    "to_name": recreation_input[index]["name"],
                    "to_mile": recreation_input[index]["milepost"],
                    "source_id": RECREATION_SOURCE_ID,
                    "mile_distance": round(
                        mile_distance(access, recreation_input[index]["milepost"]), 2
                    ),
                }
            )
        for feature in features:
            if feature["id"] == access_id:
                continue
            distance = mile_distance(access, feature["mile"])
            if distance <= 1.0:
                relationships.append(
                    {
                        "relationship_type": "nearby",
                        "from_id": access_id,
                        "to_id": feature["id"],
                        "to_name": feature["name"],
                        "to_mile": feature["mile"],
                        "source_id": None,
                        "mile_distance": round(distance, 2),
                    }
                )
    relationships.sort(
        key=lambda item: (
            item["relationship_type"],
            item["from_id"],
            item["mile_distance"],
            item["to_id"],
        )
    )

    valid_targets = {record["id"] for record in features}
    if any(item["to_id"] not in valid_targets for item in relationships):
        raise ReferenceDataError("relationship refers to an unknown feature")

    return {
        "access_points": access_points,
        "locks": locks,
        "features": features,
        "relationships": relationships,
        "counts": {
            "access_points": len(access_points),
            "locks": len(locks),
            "features": len(features),
            "relationships": len(relationships),
            "recreation_features": len(recreation_features),
        },
    }


__all__ = [
    "AMENITY_FIELDS",
    "CANAL_MILES",
    "SCHEMA_VERSION",
    "build_records",
    "load_access_points",
    "load_locks",
    "load_recreation_guide",
    "mile_distance",
    "names_match",
    "point_at_mile",
    "stable_ids",
]
