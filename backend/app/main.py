from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .api.routes import router
from .config import ROOT, settings
from .database import Base, engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield
app = FastAPI(title="SatyaLens", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","), allow_methods=["GET","POST"], allow_headers=["Content-Type"])
app.include_router(router, prefix="/api")
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
