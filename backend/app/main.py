from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.instagram import router as instagram_router
from app.core.config import settings
from app.db.session import Base, engine
from app.models import models  # noqa: F401 - ensure models are registered

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Instagram Wrapper API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(instagram_router)


@app.get("/health")
def health():
    return {"ok": True}
