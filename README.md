# Geospatial File Measurement API (FastAPI)

Backend service that accepts a geospatial file (**`.zip` Shapefile** or **`.kml`**),
extracts its features, and returns **area / length measurements** with correct CRS handling.

## 1. Setup — run locally

```bash
cd geospatial
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload
# API: http://127.0.0.1:8000 | Docs: http://127.0.0.1:8000/docs | Health: /health
```

Config via env (prefix `GEO_`): `GEO_UPLOAD_DIR`, `GEO_DATABASE_URL`, `GEO_MAX_UPLOAD_MB`.
SQLite is default (`geospatial.db`) — no external DB needed.

## 2. API

### Upload & process — `POST /api/files/`
`multipart/form-data` with field `file`: `.zip` (containing `.shp/.shx/.dbf`) or `.kml`.

```bash
curl -X POST http://127.0.0.1:8000/api/files/ -F "file=@survey.kml"
curl -X POST http://127.0.0.1:8000/api/files/ -F "file=@boundaries.zip"
```

Success `201`:
```json
{"id": "abc123", "filename": "survey.kml", "feature_count": 120, "crs": "EPSG:4326", "status": "COMPLETED"}
```
Errors: `400` wrong extension · `422` unparsable/empty file (no `.shp` in zip, 0 features, bad KML).

### File info — `GET /api/files/{id}/`
```bash
curl http://127.0.0.1:8000/api/files/abc123/
```
```json
{"id": "abc123", "filename": "survey.kml", "feature_count": 120, "crs": "EPSG:4326", "status": "COMPLETED"}
```

### Measurements — `GET /api/files/{id}/measurements/`
```bash
curl http://127.0.0.1:8000/api/files/abc123/measurements/
```
```json
{
  "id": "abc123", "filename": "survey.kml",
  "crs": "EPSG:4326", "measurement_crs": "EPSG:32644",
  "feature_count": 2,
  "measurements": [
    {"feature_id": 0, "geometry_type": "Polygon", "crs": "EPSG:4326",
     "properties": {"name": "Plot A"},
     "measurement": {"type": "area", "value": 45210.5, "unit": "sq_meters", "hectares": 4.52, "sq_km": 0.045},
     "geometry": {"type": "Polygon", "coordinates": [...]}},
    {"feature_id": 1, "geometry_type": "LineString", "crs": "EPSG:4326",
     "properties": {"name": "Road 1"},
     "measurement": {"type": "length", "value": 1240.3, "unit": "meters", "km": 1.24},
     "geometry": {...}}
  ]
}
```
Points → `"measurement": null`. Unsupported types (e.g. `GeometryCollection`) → `{"type":"unsupported",...}`, never a crash. `409` if file `FAILED`/`PROCESSING`.

## 3. Architecture

```
app/
  main.py            # FastAPI app, router wiring, table creation
  config.py          # pydantic-settings (upload dir, DB URL)
  database.py        # SQLAlchemy engine/session (SQLite)
  models.py          # GeoFile: id, filename, file_type, crs, feature_count, status, features_json
  schemas.py         # FileInfoResponse, MeasurementsResponse
  routers/files.py   # POST /api/files/, GET /{id}/, GET /{id}/measurements/
  services/
    parser.py        # .zip→find .shp→read; .kml→read (Fiona KML driver); zip-slip guard
    crs_utils.py     # geographic? → pick UTM; projected? → keep
    measurements.py  # area/length in projected CRS, per-feature record
uploads/{id}/        # stored originals (git-ignored)
```

**File-processing flow:** upload → UUID → save to `uploads/{id}/` → `PROCESSING` row → `read_geospatial()` (GeoPandas/Fiona) → missing CRS defaults to EPSG:4326 → features+measurements JSON persisted → `COMPLETED` (or `FAILED` + `422`).

**Measurement flow:** `select_measurement_crs()` → `gdf.to_crs(...)` → per geometry: Polygon/MultiPolygon→`area`, LineString/MultiLineString→`length`, Point→`null`, other→`unsupported` with note. One bad geometry can't fail the file (try/except per feature). Units: m² (+ha, km²) and m (+km).

**CRS handling:** never measure in degrees. If source is geographic (EPSG:4326) compute dataset centroid in lon/lat → UTM zone `floor((lon+180)/6)+1` → `EPSG:326xx` (N) / `327xx` (S). If already projected, measure natively. Missing CRS assumed 4326.

## 4. Design decisions & alternatives

| Decision | Chosen | Alternative | Why |
|---|---|---|---|
| Framework | FastAPI | Django+DRF | Assignment allows either; FastAPI = less boilerplate, native async, auto OpenAPI for a 3-endpoint file service |
| Geo stack | GeoPandas + Shapely + PyProj + Fiona | raw Fiona/GDAL, Django GIS | GeoPandas handles Shapefile+KML uniformly, `to_crs` one-liner; GDAL-only is more verbose |
| DB | SQLite + SQLAlchemy, features as JSON | Postgres+PostGIS | Zero-ops local run; PostGIS is the right production upgrade for spatial indexing |
| Measurement CRS | Local UTM from centroid | EPSG:3857 everywhere | 3857 distorts area badly off-equator; UTM preserves local area/length |
| Processing | Synchronous in request | Celery/RQ background job | Simple + correct for ≤50 MB; background queue is the scaling path (see Future scope) |

## 5. Learnings

- Degrees aren't meters: area/length must be computed after `to_crs()` to a projected system; UTM-by-centroid is a robust default.
- KML needs `fiona.drvsupport.supported_drivers["KML"]="rw"` — disabled by default, easy to miss.
- Shapefile = multi-file format; zips must be scanned for `.shp` and guarded against zip-slip paths.
- Defensive per-feature measurement keeps one corrupt geometry from failing a 10k-feature upload.

## 6. Future scope

- Async/background processing (Celery + Redis) with `PROCESSING` polling for large files.
- Postgres + PostGIS, S3-backed uploads, auth/rate-limiting, pagination on measurements.
- Reprojection choice per use-case (equal-area for global area stats), on-the-fly GeoJSON map preview endpoint.
