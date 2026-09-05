"""Public source and artifact provenance."""

from __future__ import annotations

from typing import Any

from canawler.dataset import (
    ACCESS_SOURCE_ID,
    NPS_LOCK_SOURCE_ID,
    RECREATION_SOURCE_ID,
    TOWPATH_SOURCE_ID,
    TRUST_LOCK_SOURCE_ID,
    load_access_points,
    load_locks,
    load_recreation_guide,
)
from canawler.reference import FEATURESERVER_URL, ReferenceDataError


def build_sources() -> dict[str, Any]:
    access = load_access_points()["source"]
    recreation = load_recreation_guide()["source"]
    lock_sources = load_locks()["sources"]
    lock_by_role = {source["role"]: source for source in lock_sources}
    try:
        nps_locks = lock_by_role["Lift-lock count and numbering authority"]
        trust_locks = lock_by_role["Primary practical lock mileposts and common names"]
    except KeyError as error:
        raise ReferenceDataError(
            "lock source roles do not match the expected schema"
        ) from error

    sources = sorted(
        [
            {
                "id": ACCESS_SOURCE_ID,
                "name": access["name"],
                "organization": "C&O Canal Association",
                "url": access["url"],
                "description": "Access-point names, mile ranges, and coordinates.",
            },
            {
                "id": RECREATION_SOURCE_ID,
                "name": recreation["name"],
                "organization": "National Park Service",
                "url": recreation["url"],
                "description": "Recreation locations and listed visitor amenities.",
            },
            {
                "id": NPS_LOCK_SOURCE_ID,
                "name": "National Park Service Lift Locks",
                "organization": "National Park Service",
                "url": nps_locks["url"],
                "description": "Authority for the lift-lock count and numbering.",
            },
            {
                "id": TRUST_LOCK_SOURCE_ID,
                "name": trust_locks["name"],
                "organization": "C&O Canal Trust",
                "url": trust_locks["url"],
                "description": "Practical lift-lock mileposts and common names.",
            },
            {
                "id": TOWPATH_SOURCE_ID,
                "name": "National Park Service Public Trails dataset",
                "organization": "National Park Service",
                "url": FEATURESERVER_URL,
                "description": (
                    "Underlying geometry for the canonical C&O Canal towpath."
                ),
            },
        ],
        key=lambda source: source["id"],
    )
    artifacts = {
        "access-points": [ACCESS_SOURCE_ID, RECREATION_SOURCE_ID],
        "features": [
            ACCESS_SOURCE_ID,
            NPS_LOCK_SOURCE_ID,
            RECREATION_SOURCE_ID,
            TOWPATH_SOURCE_ID,
            TRUST_LOCK_SOURCE_ID,
        ],
        "locks": [NPS_LOCK_SOURCE_ID, TRUST_LOCK_SOURCE_ID, TOWPATH_SOURCE_ID],
        "relationships": [
            ACCESS_SOURCE_ID,
            NPS_LOCK_SOURCE_ID,
            RECREATION_SOURCE_ID,
            TRUST_LOCK_SOURCE_ID,
        ],
        "towpath.geojson": [TOWPATH_SOURCE_ID],
    }
    return {"schema_version": 1, "sources": sources, "artifacts": artifacts}


__all__ = ["build_sources"]
