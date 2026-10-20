from contextlib import asynccontextmanager

from fastapi import FastAPI
from psycopg import OperationalError

from app.api.stac_api import router, database_unavailable
from app.database import pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open(wait=True)
    yield
    pool.close()


app = FastAPI(lifespan=lifespan)
app.include_router(router)
app.add_exception_handler(OperationalError, database_unavailable)
