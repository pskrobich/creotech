from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.stac_api import router
from app.database import pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open(wait=True)
    yield
    pool.close()


app = FastAPI(lifespan=lifespan)
app.include_router(router)
