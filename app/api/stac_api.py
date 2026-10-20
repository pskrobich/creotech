import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pyproj.exceptions import CRSError
from pystac.errors import STACValidationError
from shapely.errors import GEOSException

from app.exceptions import UnsupportedFormatError, UnsupportedMediaTypeError
from app.model.search import SearchRequest
from app.service.stac_service import search_stac_items, upsert_stac_item

INGEST_REQUEST_URL = "/ingest"
SEARCH_REQUEST_URL = "/search"
V1_REQUEST_MAPPING = "/v1"
INVALID_METADATA_ERRORS = (
    KeyError,
    ValueError,
    TypeError,
    AttributeError,
    STACValidationError,
    GEOSException,
    CRSError,
)

router = APIRouter(prefix=V1_REQUEST_MAPPING)
logger = logging.getLogger(__name__)


@router.put(path=INGEST_REQUEST_URL)
async def ingest(request: Request) -> Response:
    body = await request.body()
    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    try:
        created = await run_in_threadpool(upsert_stac_item, body, media_type)
    except UnsupportedMediaTypeError as e:
        raise HTTPException(status_code=415, detail=str(e)) from e
    except UnsupportedFormatError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except INVALID_METADATA_ERRORS as e:
        raise HTTPException(status_code=422, detail=f"Invalid metadata: {e}") from e
    return Response(status_code=201 if created else 204)


@router.get(path=SEARCH_REQUEST_URL)
def search(search_request: Annotated[SearchRequest, Query()]) -> list[dict]:
    items = search_stac_items(search_request)
    return [item.to_dict() for item in items]


async def database_unavailable(_request: Request, _exc: Exception) -> JSONResponse:
    logger.exception("Database unavailable")
    return JSONResponse(status_code=503, content={"detail": "Database is temporarily unavailable"})
