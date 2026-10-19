import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Request, Response, HTTPException, Query
from fastapi.responses import JSONResponse
from psycopg import OperationalError
from pyproj.exceptions import CRSError
from pystac.errors import STACValidationError
from shapely.errors import GEOSException

from app.adapters.base_adapter import UnsupportedFormatError, UnsupportedMediaTypeError
from app.database import pool
from app.model.search import SearchRequest
from app.service.stac_service import upsert_stac_item, search_stac_items

INGEST_REQUEST_URL = "/v1/ingest"
SEARCH_REQUEST_URL = "/v1/search"
INVALID_METADATA_ERRORS = (
    KeyError,
    ValueError,
    TypeError,
    AttributeError,
    STACValidationError,
    GEOSException,
    CRSError,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open(wait=True)
    yield
    pool.close()


app = FastAPI(lifespan=lifespan)
logger = logging.getLogger(__name__)


@app.put(path=INGEST_REQUEST_URL)
async def ingest(request: Request) -> Response:
    body = await request.body()
    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    try:
        created = upsert_stac_item(body, media_type)
    except UnsupportedMediaTypeError as e:
        raise HTTPException(status_code=415, detail=str(e)) from e
    except UnsupportedFormatError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except INVALID_METADATA_ERRORS as e:
        raise HTTPException(status_code=422, detail=f"Invalid metadata: {e}") from e
    return Response(status_code=201 if created else 204)


@app.get(path=SEARCH_REQUEST_URL)
def search(search_request: Annotated[SearchRequest, Query()]) -> list[dict]:
    items = search_stac_items(search_request)
    return [item.to_dict() for item in items]
