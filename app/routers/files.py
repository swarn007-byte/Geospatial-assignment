"""POST /api/files/ | GET /api/files/{id}/ | GET /api/files/{id}/measurements/"""
import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.database import get_db
from app.services.measurements import build_features_with_measurements
from app.services.parser import detect_file_type, read_geospatial

router = APIRouter(prefix="/api/files", tags=["files"])


def _record_to_info(rec: models.GeoFile) -> dict:
    return {
        "id": rec.id,
        "filename": rec.filename,
        "feature_count": rec.feature_count,
        "crs": rec.crs,
        "status": rec.status,
    }


@router.post("/", response_model=schemas.FileInfoResponse, status_code=201)
def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")
    try:
        file_type = detect_file_type(file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    file_id = uuid.uuid4().hex[:12]
    workdir = Path(settings.upload_dir) / file_id
    workdir.mkdir(parents=True, exist_ok=True)
    stored = workdir / file.filename
    with open(stored, "wb") as out:
        shutil.copyfileobj(file.file, out)

    rec = models.GeoFile(
        id=file_id, filename=file.filename, file_type=file_type, status="PROCESSING"
    )
    db.add(rec)
    db.commit()

    try:
        gdf = read_geospatial(stored, file_type)
        features, source_crs, measurement_crs = build_features_with_measurements(gdf)
        rec.features_json = json.dumps(
            {"features": features, "measurement_crs": measurement_crs}
        )
        rec.crs = source_crs
        rec.feature_count = len(features)
        rec.status = "COMPLETED"
    except ValueError as exc:
        rec.status = "FAILED"
        rec.error = str(exc)
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(rec)
    return _record_to_info(rec)


@router.get("/{file_id}/", response_model=schemas.FileInfoResponse)
def get_file_info(file_id: str, db: Session = Depends(get_db)):
    rec = db.get(models.GeoFile, file_id)
    if not rec:
        raise HTTPException(status_code=404, detail="File not found.")
    return _record_to_info(rec)


@router.get("/{file_id}/measurements/", response_model=schemas.MeasurementsResponse)
def get_measurements(file_id: str, db: Session = Depends(get_db)):
    rec = db.get(models.GeoFile, file_id)
    if not rec:
        raise HTTPException(status_code=404, detail="File not found.")
    if rec.status != "COMPLETED":
        raise HTTPException(
            status_code=409, detail=f"File status is {rec.status}: {rec.error or 'not ready'}"
        )
    payload = json.loads(rec.features_json or "{}")
    measurements = [
        {
            "feature_id": f["index"],
            "geometry_type": f["geometry_type"],
            "crs": rec.crs,
            "properties": f.get("properties", {}),
            "measurement": f.get("measurement"),
            "geometry": f.get("geometry"),
        }
        for f in payload.get("features", [])
    ]
    return {
        "id": rec.id,
        "filename": rec.filename,
        "crs": rec.crs,
        "measurement_crs": payload.get("measurement_crs"),
        "feature_count": rec.feature_count,
        "measurements": measurements,
    }
