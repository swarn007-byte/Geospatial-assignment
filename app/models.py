import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class GeoFile(Base):
    __tablename__ = "geo_files"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    crs = Column(String, nullable=True)
    feature_count = Column(Integer, default=0)
    status = Column(String, default="PROCESSING")
    error = Column(Text, nullable=True)
    features_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
