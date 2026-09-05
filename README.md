# Canawler

**The C&O Canal, structured as data.**

Canawler is a reproducible, source-aware public dataset for exploring the
184.5-mile Chesapeake & Ohio Canal corridor. It publishes a canonical feature
index, access points and amenities, all 74 lift locks, nearby and source-match
relationships, source metadata, and the towpath geometry.

Personal activity and completion tracking are intentionally out of scope. The
core dataset builds without Strava data or network access.

## Public data

Stable outputs live in [`data/public/`](data/public/):

| Dataset | Description |
| --- | --- |
| `features` | Small common index of access points, locks, and NPS recreation features |
| `access-points` | Access locations, coordinates, mile ranges, and matched NPS amenities |
| `locks` | Lift-lock numbers, names, mileposts, and towpath-derived coordinates |
| `relationships` | Access-point proximity links and explicit reference-source matches |
| `sources` | Source registry and artifact-to-source provenance |
| `towpath.geojson` | Canonical Georgetown-to-Cumberland route geometry |

CSV is intended for analysis. JSON preserves lists and structured amenity data.
IDs are deterministic join keys; missing values are `null` in JSON and empty in
CSV. Nearby relationships use milepost distance and a one-mile threshold. A
`source_match` connects an access record to the corresponding NPS feature while
preserving the NPS name and milepost used by the match.

## Sources

Committed inputs in [`data/reference/`](data/reference/) come from the National
Park Service Public Trails and recreation guide, the C&O Canal Association access
guide, and the C&O Canal Trust lock collection. The NPS supplies lock count and
numbering authority. Machine-readable URLs and artifact relationships are in
[`sources.json`](data/public/json/sources.json); towpath acquisition details are
documented beside the [canonical geometry](data/reference/co-towpath/README.md).

## Build and test

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```console
uv sync
uv run python -m canawler.build
uv run pytest
```

The build validates reference schemas, identifiers, coordinates, mile values,
source references, relationships, and deterministic ordering before writing CSV,
JSON, and GeoJSON. To validate the committed towpath or deliberately refresh it
from NPS:

```console
uv run python -m canawler.reference validate
uv run python -m canawler.reference inspect
uv run python -m canawler.reference build
```

The last two commands require network access and are maintenance operations, not
part of a routine build.

## Website

The Quarto site reads only committed public outputs.

```console
quarto preview
quarto render
```

Rendered output is written to the ignored `_site/` directory. Pushes to `main`
render and publish the site to GitHub Pages.
