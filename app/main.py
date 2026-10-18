from fastapi import FastAPI, Request, HTTPException
from pyproj.exceptions import CRSError
from pystac.errors import STACValidationError
from shapely.errors import GEOSException

from app.adapters.base_adapter import UnsupportedFormatError, UnsupportedMediaTypeError
from app.service.stac_service import store_stac_item

INVALID_METADATA_ERRORS = (
    KeyError,
    ValueError,
    TypeError,
    AttributeError,
    STACValidationError,
    GEOSException,
    CRSError,
)

app = FastAPI()


@app.post(
    path="/ingest",
    status_code=201
)
async def ingest(request: Request) -> dict:
    body = await request.body()
    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    try:
        item = store_stac_item(body, media_type)
    except UnsupportedMediaTypeError as e:
        raise HTTPException(status_code=415, detail=str(e)) from e
    except UnsupportedFormatError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except INVALID_METADATA_ERRORS as e:
        raise HTTPException(status_code=422, detail=f"Invalid metadata: {e}") from e
    return item.to_dict()
