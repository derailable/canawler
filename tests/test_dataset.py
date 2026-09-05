from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from canawler.build import build_public_data
from canawler.dataset import (
    build_records,
    load_access_points,
    load_locks,
    load_recreation_guide,
    names_match,
)
from canawler.geography import (
    GeographyError,
    milepost_intervals_to_geometries,
    point_at_mile,
)
from canawler.provenance import build_sources
from canawler.reference import ReferenceDataError, validate_canonical_reference
from canawler.validation import validate_public_records


def test_reference_inputs_and_geometry_validate() -> None:
    geometry = validate_canonical_reference()

    assert len(geometry.coords) == 9_907
    assert len(load_access_points()["access_points"]) == 81
    assert len(load_locks()["locks"]) == 74
    assert len(load_recreation_guide()["locations"]) == 79


def test_public_records_have_stable_unique_ids_and_known_sources() -> None:
    records = build_records(validate_canonical_reference())
    sources = build_sources()

    validate_public_records(records, sources)
    assert records["counts"] == {
        "access_points": 81,
        "locks": 74,
        "features": 221,
        "relationships": 286,
        "recreation_features": 66,
    }
    assert records["features"][0]["id"] == "access-georgetown-0-0"
    assert records["features"][-1]["id"] == "nps-canal-terminus-cumberland-184-5"


def test_milepoint_linear_reference_reaches_both_endpoints() -> None:
    geometry = validate_canonical_reference()

    assert point_at_mile(geometry, 0) == pytest.approx(
        (geometry.coords[0][1], geometry.coords[0][0]), abs=1e-6
    )
    assert point_at_mile(geometry, 184.5) == pytest.approx(
        (geometry.coords[-1][1], geometry.coords[-1][0]), abs=1e-6
    )


def test_milepost_intervals_create_valid_route_segments() -> None:
    geometry = validate_canonical_reference()

    segments = milepost_intervals_to_geometries(geometry, [(0, 1), (100, 101)])

    assert len(segments) == 2
    assert all(segment.is_valid and not segment.is_empty for segment in segments)
    with pytest.raises(GeographyError, match="start must be less"):
        milepost_intervals_to_geometries(geometry, [(10, 10)])


@pytest.mark.parametrize(
    ("access_name", "nps_name", "expected"),
    [
        ("Fletchers Cove", "Fletchers Cove", True),
        ("Lock 7", "Lock 7 (Glen Echo)", True),
        ("Monocacy Aqueduct", "Monocacy Bridge", False),
    ],
)
def test_name_matching(access_name: str, nps_name: str, expected: bool) -> None:
    assert names_match(access_name, nps_name) is expected


def test_validation_rejects_duplicate_feature_ids() -> None:
    records = build_records(validate_canonical_reference())
    broken = copy.deepcopy(records)
    broken["features"][1]["id"] = broken["features"][0]["id"]

    with pytest.raises(ReferenceDataError, match="IDs must be unique"):
        validate_public_records(broken, build_sources())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("latitude", 91, "latitude is invalid"),
        ("mile", 185, "mile is outside the canal"),
        ("source_ids", ["unknown"], "unknown sources"),
    ],
)
def test_validation_rejects_bad_feature_values(
    field: str, value: object, message: str
) -> None:
    records = build_records(validate_canonical_reference())
    broken = copy.deepcopy(records)
    broken["features"][0][field] = value

    with pytest.raises(ReferenceDataError, match=message):
        validate_public_records(broken, build_sources())


def test_build_is_deterministic_and_matches_committed_outputs(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    build_public_data(first)
    build_public_data(second)

    first_files = sorted(
        path.relative_to(first) for path in first.rglob("*") if path.is_file()
    )
    second_files = sorted(
        path.relative_to(second) for path in second.rglob("*") if path.is_file()
    )
    assert first_files == second_files
    assert "activities.json" not in {path.name for path in first_files}
    for relative in first_files:
        assert (first / relative).read_bytes() == (second / relative).read_bytes()
        assert (first / relative).read_bytes() == (
            Path("data/public") / relative
        ).read_bytes()


def test_source_match_relationships_are_source_aware() -> None:
    records = build_records(validate_canonical_reference())
    matches = [
        item
        for item in records["relationships"]
        if item["relationship_type"] == "source_match"
    ]

    assert matches
    assert all(item["source_id"] == "nps_recreation_guide" for item in matches)
    assert all(item["to_name"] and item["to_mile"] is not None for item in matches)


def test_corridor_specific_features_are_in_the_common_index() -> None:
    records = build_records(validate_canonical_reference())
    types = {record["feature_type"] for record in records["features"]}

    assert {"aqueduct", "dam", "railroad_junction", "railroad_station"} <= types


def test_json_outputs_are_documents_not_bare_arrays() -> None:
    features = json.loads(Path("data/public/json/features.json").read_text())

    assert features["schema_version"] == 1
    assert isinstance(features["features"], list)
