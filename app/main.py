"""FastAPI entrypoint."""
from fastapi import FastAPI

from app import models
from app.config import settings
from app.database import engine
from app.routers import files

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)
app.include_router(files.router)


@app.get("/", tags=["health"])
def root():
    return {"message": settings.app_name, "docs": "/docs"}


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
