from pystac import Item

from app.adapters.base_adapter import BaseAdapter
from app.adapters.sky_is_no_limit_adapter import SkyIsNoLimitAdapter
from app.adapters.space_is_no_limit_adapter import SpaceIsNoLimitAdapter
from app.exceptions import UnsupportedFormatError, UnsupportedMediaTypeError
from app.model.search import SearchRequest
from app.repository.stac_repository import find_items, upsert

ADAPTERS: list[BaseAdapter] = [SkyIsNoLimitAdapter(), SpaceIsNoLimitAdapter()]


def upsert_stac_item(data: bytes, media_type: str) -> bool:
    stac_item = _convert_to_stac_item(data, media_type)
    return upsert(stac_item)


def _convert_to_stac_item(data: bytes, media_type: str) -> Item:
    candidates = [adapter for adapter in ADAPTERS if media_type in adapter.media_types]
    if not candidates:
        raise UnsupportedMediaTypeError(f"Unsupported media type: {media_type}")
    for adapter in candidates:
        if adapter.matches(data):
            return adapter.to_stac_item(data)
    raise UnsupportedFormatError("Unsupported payload format")


def search_stac_items(search_request: SearchRequest) -> list[Item]:
    return find_items(search_request)
