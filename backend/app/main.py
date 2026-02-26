from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, accounts, dashboard
from app.core.config import settings
from app.db.session import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Social Auto Reply API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(dashboard.router)


@app.get("/health")
def health():
    return {"ok": True}
