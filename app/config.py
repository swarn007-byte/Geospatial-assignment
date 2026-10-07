from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Geospatial File Measurement API"
    upload_dir: str = "uploads"
    database_url: str = "sqlite:///./geospatial.db"
    max_upload_mb: int = 50

    class Config:
        env_prefix = "GEO_"


settings = Settings()
