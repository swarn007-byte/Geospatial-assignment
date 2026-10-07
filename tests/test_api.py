import geopandas as gpd
from fastapi.testclient import TestClient
from shapely.geometry import LineString, Point, Polygon

from app.main import app

client = TestClient(app)


def _mixed_kml(path: str):
    gdf = gpd.GeoDataFrame(
        {"name": ["A", "B", "C"]},
        geometry=[
            Polygon([(77.59, 12.97), (77.60, 12.97), (77.60, 12.98), (77.59, 12.98)]),
            LineString([(77.59, 12.97), (77.61, 12.99)]),
            Point(77.595, 12.975),
        ],
        crs="EPSG:4326",
    )
    gdf.to_file(path, driver="KML")


def test_kml_flow(tmp_path):
    kml = str(tmp_path / "s.kml")
    _mixed_kml(kml)
    with open(kml, "rb") as f:
        r = client.post("/api/files/", files={"file": ("s.kml", f)})
    assert r.status_code == 201, r.text
    fid = r.json()["id"]

    info = client.get(f"/api/files/{fid}/")
    assert info.status_code == 200
    assert info.json()["feature_count"] == 3

    m = client.get(f"/api/files/{fid}/measurements/")
    assert m.status_code == 200
    body = m.json()
    assert body["measurement_crs"].startswith("EPSG:326")
    by_type = {x["geometry_type"]: x["measurement"] for x in body["measurements"]}
    assert by_type["Polygon"]["type"] == "area" and by_type["Polygon"]["value"] > 0
    assert by_type["LineString"]["type"] == "length" and by_type["LineString"]["value"] > 0
    assert by_type["Point"] is None


def test_bad_extension():
    r = client.post("/api/files/", files={"file": ("x.txt", b"hi", "text/plain")})
    assert r.status_code == 400


def test_not_found():
    assert client.get("/api/files/doesnotexist/").status_code == 404
