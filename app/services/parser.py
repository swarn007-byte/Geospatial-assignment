import zipfile
from pathlib import Path

import fiona
import geopandas as gpd

fiona.drvsupport.supported_drivers["KML"] = "rw"
fiona.drvsupport.supported_drivers["LIBKML"] = "rw"

ALLOWED_EXTENSIONS = {".zip", ".kml"}


def detect_file_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".zip":
        return "shapefile"
    if suffix == ".kml":
        return "kml"
    raise ValueError(f"Unsupported file type '{suffix}'. Upload a .zip (Shapefile) or .kml file.")


def _find_shp(extract_dir: Path) -> Path:
    candidates = list(extract_dir.rglob("*.shp"))
    if not candidates:
        raise ValueError("No .shp found inside the zip. A Shapefile zip must contain .shp + .shx + .dbf.")
    return sorted(candidates, key=lambda p: len(p.parts))[0]


def read_geospatial(zip_or_kml_path: Path, file_type: str) -> gpd.GeoDataFrame:
    try:
        if file_type == "kml":
            gdf = gpd.read_file(str(zip_or_kml_path), driver="KML")
        elif file_type == "shapefile":
            extract_dir = zip_or_kml_path.parent / f"{zip_or_kml_path.stem}_extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_or_kml_path) as z:
                for member in z.namelist():
                    target = (extract_dir / member).resolve()
                    if not str(target).startswith(str(extract_dir.resolve())):
                        raise ValueError(f"Unsafe path in zip: {member}")
                z.extractall(extract_dir)
            shp = _find_shp(extract_dir)
            gdf = gpd.read_file(str(shp))
        else:
            raise ValueError(f"Unknown file_type: {file_type}")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Could not parse geospatial file: {exc}") from exc

    if gdf.empty:
        raise ValueError("File contains 0 features.")
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    return gdf
