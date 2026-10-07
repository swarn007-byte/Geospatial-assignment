"""Measurement logic: area for polygons, length for linestrings, graceful fallback."""
import json
from typing import Any

import geopandas as gpd
from shapely.geometry import mapping

from app.services.crs_utils import normalize_crs, select_measurement_crs

SUPPORTED_AREA = {"Polygon", "MultiPolygon"}
SUPPORTED_LENGTH = {"LineString", "MultiLineString"}


def _measure_single(geom_type: str, geom_projected) -> dict[str, Any] | None:
    if geom_projected is None or geom_projected.is_empty:
        return {"type": "unsupported", "value": None, "unit": None, "note": "Empty geometry"}
    if geom_type in SUPPORTED_AREA:
        area = float(geom_projected.area)
        return {
            "type": "area",
            "value": area,
            "unit": "sq_meters",
            "hectares": area / 10_000,
            "sq_km": area / 1_000_000,
        }
    if geom_type in SUPPORTED_LENGTH:
        length = float(geom_projected.length)
        return {"type": "length", "value": length, "unit": "meters", "km": length / 1_000}
    if geom_type in {"Point", "MultiPoint"}:
        return None  # No measurement required for points
    # Anything else (GeometryCollection, etc.): graceful, no crash
    return {"type": "unsupported", "value": None, "unit": None, "note": f"No measurement for {geom_type}"}


def build_features_with_measurements(gdf: gpd.GeoDataFrame) -> tuple[list[dict], str, str | None]:
    """
    Returns (features, source_crs, measurement_crs).
    Each feature: {index, geometry_type, geometry(geojson), properties, measurements}
    """
    source_crs = normalize_crs(gdf.crs)
    measurement_crs = select_measurement_crs(gdf)
    projected = gdf.to_crs(measurement_crs)

    # Properties = all non-geometry columns
    prop_cols = [c for c in gdf.columns if c != gdf.geometry.name]

    features: list[dict] = []
    for idx, (orig_row, proj_row) in enumerate(zip(gdf.itertuples(), projected.itertuples())):
        geom = getattr(orig_row, gdf.geometry.name)
        proj_geom = getattr(proj_row, projected.geometry.name)
        geom_type = geom.geom_type if geom is not None else "Unknown"
        try:
            measurement = _measure_single(geom_type, proj_geom)
        except Exception as exc:  # never let one bad geometry kill the file
            measurement = {"type": "unsupported", "value": None, "unit": None, "note": f"Error: {exc}"}

        props = {}
        for col in prop_cols:
            val = gdf.iloc[idx][col]
            try:
                json.dumps(val)  # ensure JSON-serializable
                props[col] = val
            except TypeError:
                props[col] = str(val)

        features.append(
            {
                "index": idx,
                "geometry_type": geom_type,
                "geometry": mapping(geom) if geom is not None else None,
                "properties": props,
                "measurement": measurement,
            }
        )
    return features, source_crs, measurement_crs
