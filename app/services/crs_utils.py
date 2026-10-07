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
    if crs is None:
        return False
    try:
        return CRS.from_user_input(crs).is_geographic
    except Exception:
        return False


def utm_epsg_for_lonlat(lon: float, lat: float) -> str:
    zone = int((lon + 180) // 6) + 1
    if lat >= 0:
        return f"EPSG:{32600 + zone}"
    return f"EPSG:{32700 + zone}"


def select_measurement_crs(gdf: gpd.GeoDataFrame) -> str:
    if gdf.crs is not None and not is_geographic(gdf.crs):
        return normalize_crs(gdf.crs)

    work = gdf
    if work.crs is None:
        work = work.set_crs(epsg=4326)
    else:
        work = work.to_crs(epsg=4326)
    centroid = work.geometry.union_all().centroid
    return utm_epsg_for_lonlat(float(centroid.x), float(centroid.y))
