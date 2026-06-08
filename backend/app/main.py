from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.core.database import engine, Base
from app.routes import auth, predictions, retrain
from app.ml.model import load_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables + load model
    Base.metadata.create_all(bind=engine)
    load_model()
    yield
    # Shutdown: nothing to clean up for now


app = FastAPI(
    title="Network Threat Analyzer API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(predictions.router)
app.include_router(retrain.router)


@app.get("/health")
def health():
    return {"status": "ok"}
