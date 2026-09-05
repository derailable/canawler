"""Build Canawler's deterministic public datasets from committed references."""

from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from canawler.dataset import AMENITY_FIELDS, SCHEMA_VERSION, build_records
from canawler.provenance import build_sources
from canawler.reference import (
    DEFAULT_OUTPUT,
    ReferenceDataError,
    validate_canonical_reference,
)
from canawler.validation import validate_public_records

PUBLIC_DIR = Path("data/public")

FEATURE_COLUMNS = (
    "id",
    "name",
    "feature_type",
    "mile",
    "mile_end",
    "latitude",
    "longitude",
    "source_ids",
)
ACCESS_COLUMNS = (
    "id",
    "name",
    "mile",
    "mile_end",
    "latitude",
    "longitude",
    "has_amenity_data",
    *AMENITY_FIELDS,
    "source_ids",
)
LOCK_COLUMNS = (
    "id",
    "lock_number",
    "name",
    "common_name",
    "mile",
    "alternate_mile",
    "latitude",
    "longitude",
    "notes",
    "source_ids",
)
RELATIONSHIP_COLUMNS = (
    "relationship_type",
    "from_id",
    "to_id",
    "to_name",
    "to_mile",
    "mile_distance",
    "source_id",
)
SOURCE_COLUMNS = ("id", "name", "organization", "url", "description")


@dataclass(frozen=True)
class BuildReport:
    files: tuple[Path, ...]
    access_points: int
    locks: int
    features: int
    relationships: int

    def format(self) -> str:
        return "\n".join(
            (
                f"Access points: {self.access_points}",
                f"Locks: {self.locks}",
                f"Features: {self.features}",
                f"Relationships: {self.relationships}",
                f"Public files: {len(self.files)}",
                f"Output: {self.files[0].parents[1]}",
            )
        )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")


def _json_text(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return "|".join(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _csv_text(records: list[dict[str, Any]], columns: tuple[str, ...]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=columns,
        extrasaction="ignore",
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for record in records:
        writer.writerow({key: _csv_value(record.get(key)) for key in columns})
    return stream.getvalue()


def _access_csv(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        amenities = record["amenities"]
        rows.append(
            {
                **record,
                "has_amenity_data": amenities is not None,
                **(
                    {field: amenities[field] for field in AMENITY_FIELDS}
                    if amenities is not None
                    else {field: None for field in AMENITY_FIELDS}
                ),
            }
        )
    return rows


def build_public_data(output_directory: Path = PUBLIC_DIR) -> BuildReport:
    """Validate committed references and write stable JSON, CSV, and GeoJSON."""
    geometry = validate_canonical_reference()
    records = build_records(geometry)
    sources = build_sources()
    validate_public_records(records, sources)

    output_directory = Path(output_directory)
    json_dir = output_directory / "json"
    csv_dir = output_directory / "csv"
    documents = {
        "access-points": {
            "schema_version": SCHEMA_VERSION,
            "access_points": records["access_points"],
        },
        "features": {"schema_version": SCHEMA_VERSION, "features": records["features"]},
        "locks": {"schema_version": SCHEMA_VERSION, "locks": records["locks"]},
        "relationships": {
            "schema_version": SCHEMA_VERSION,
            "relationships": records["relationships"],
        },
        "sources": sources,
    }
    files: list[Path] = []
    for name, document in documents.items():
        path = json_dir / f"{name}.json"
        _write_text(path, _json_text(document))
        files.append(path)

    csv_outputs = {
        "access-points": (_access_csv(records["access_points"]), ACCESS_COLUMNS),
        "features": (records["features"], FEATURE_COLUMNS),
        "locks": (records["locks"], LOCK_COLUMNS),
        "relationships": (records["relationships"], RELATIONSHIP_COLUMNS),
        "sources": (sources["sources"], SOURCE_COLUMNS),
    }
    for name, (rows, columns) in csv_outputs.items():
        path = csv_dir / f"{name}.csv"
        _write_text(path, _csv_text(rows, columns))
        files.append(path)

    towpath_path = output_directory / "towpath.geojson"
    towpath_path.parent.mkdir(parents=True, exist_ok=True)
    if (
        not towpath_path.exists()
        or towpath_path.read_bytes() != DEFAULT_OUTPUT.read_bytes()
    ):
        shutil.copyfile(DEFAULT_OUTPUT, towpath_path)
    files.append(towpath_path)

    counts = records["counts"]
    return BuildReport(
        files=tuple(files),
        access_points=counts["access_points"],
        locks=counts["locks"],
        features=counts["features"],
        relationships=counts["relationships"],
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m canawler.build",
        description="Build the public Canawler dataset from committed references.",
    )
    parser.add_argument(
        "--output", type=Path, default=PUBLIC_DIR, help="public output directory"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        print(build_public_data(args.output).format())
    except ReferenceDataError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["BuildReport", "build_public_data", "main"]
