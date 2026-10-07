"""CRS helpers: never measure in degrees; pick a projected CRS per dataset."""
from typing import Optional

import geopandas as gpd
from pyproj import CRS


def normalize_crs(crs) -> Optional[str]:
    if crs is None:
        return None
    try:
        return CRS.from_user_input(crs).to_string()
    except Exception:
        return str(crs)


def is_geographic(crs) -> bool:
    """True if CRS uses lat/lon degrees (e.g. EPSG:4326)."""
    if crs is None:
        return False
    try:
        return CRS.from_user_input(crs).is_geographic
    except Exception:
        return False


def utm_epsg_for_lonlat(lon: float, lat: float) -> str:
    """Return best-fit UTM EPSG string for a lon/lat point."""
    zone = int((lon + 180) // 6) + 1
    if lat >= 0:
        return f"EPSG:{32600 + zone}"  # WGS84 / UTM north
    return f"EPSG:{32700 + zone}"  # WGS84 / UTM south


def select_measurement_crs(gdf: gpd.GeoDataFrame) -> str:
    """
    Strategy for measurement CRS:
    1. If source CRS is already projected -> measure in it.
    2. If geographic (EPSG:4326 etc.) -> reproject a copy to local UTM
       derived from the dataset centroid.
    3. If CRS is missing -> assume EPSG:4326, then UTM.

    Alternatives considered: EPSG:3857 (Web-Mercator, simple but distorts
    area badly away from equator) and global equal-area like EPSG:6933
    (good for area, worse for local distance). Local UTM is the best
    general-purpose compromise for both area and length.
    """
    if gdf.crs is not None and not is_geographic(gdf.crs):
        return normalize_crs(gdf.crs)

    # Need lon/lat centroid to pick UTM zone.
    work = gdf
    if work.crs is None:
        work = work.set_crs(epsg=4326)
    else:
        work = work.to_crs(epsg=4326)
    centroid = work.geometry.union_all().centroid
    return utm_epsg_for_lonlat(float(centroid.x), float(centroid.y))
