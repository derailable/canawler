"""Source-neutral geographic utilities for the C&O Canal linear reference."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable

from pyproj import Transformer
from shapely.geometry import LineString
from shapely.ops import substring, transform

CANAL_MILES = 184.5
MATCH_CRS = "EPSG:5070"

_TO_METERS = Transformer.from_crs("EPSG:4326", MATCH_CRS, always_xy=True)
_TO_WGS84 = Transformer.from_crs(MATCH_CRS, "EPSG:4326", always_xy=True)


class GeographyError(ValueError):
    """A geographic operation cannot be performed safely."""


def _projected_reference(reference: LineString) -> LineString:
    if (
        reference.geom_type != "LineString"
        or reference.is_empty
        or not reference.is_valid
        or reference.length <= 0
    ):
        raise GeographyError("reference must be one valid, nonempty LineString")
    projected = transform(_TO_METERS.transform, reference)
    if projected.length <= 0:
        raise GeographyError("projected reference has zero length")
    return projected


def milepoint_locator(reference: LineString) -> Callable[[float], tuple[float, float]]:
    """Build an efficient latitude/longitude lookup for official canal miles."""
    projected = _projected_reference(reference)

    def locate(milepost: float) -> tuple[float, float]:
        if not math.isfinite(milepost) or not 0 <= milepost <= CANAL_MILES:
            raise GeographyError(f"milepost must be between 0 and {CANAL_MILES}")
        point = transform(
            _TO_WGS84.transform,
            projected.interpolate(milepost / CANAL_MILES, normalized=True),
        )
        return round(point.y, 6), round(point.x, 6)

    return locate


def point_at_mile(reference: LineString, milepost: float) -> tuple[float, float]:
    """Return the WGS84 latitude and longitude at an official canal mile."""
    return milepoint_locator(reference)(milepost)


def milepost_intervals_to_geometries(
    reference: LineString, intervals: Iterable[tuple[float, float]]
) -> tuple[LineString, ...]:
    """Slice a WGS84 route using the official 0–184.5 mile coordinate."""
    projected = _projected_reference(reference)
    geometries: list[LineString] = []
    for index, interval in enumerate(intervals):
        try:
            start_raw, end_raw = interval
            start = float(start_raw)
            end = float(end_raw)
        except (TypeError, ValueError) as error:
            raise GeographyError(f"mile interval {index} is malformed") from error
        if not math.isfinite(start) or not math.isfinite(end):
            raise GeographyError(f"mile interval {index} must contain finite values")
        if not 0 <= start <= CANAL_MILES or not 0 <= end <= CANAL_MILES:
            raise GeographyError(
                f"mile interval {index} is outside 0-{CANAL_MILES} miles"
            )
        if start >= end:
            raise GeographyError(
                f"mile interval {index} start must be less than its end"
            )
        piece = substring(
            projected,
            start / CANAL_MILES,
            end / CANAL_MILES,
            normalized=True,
        )
        geometry = transform(_TO_WGS84.transform, piece)
        if geometry.geom_type != "LineString" or geometry.is_empty:
            raise GeographyError(f"mile interval {index} produced no line geometry")
        geometries.append(geometry)
    return tuple(geometries)


__all__ = [
    "CANAL_MILES",
    "GeographyError",
    "milepoint_locator",
    "milepost_intervals_to_geometries",
    "point_at_mile",
]
