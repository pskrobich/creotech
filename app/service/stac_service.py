from pystac import Item

from app.adapters.base_adapter import UnsupportedFormatError, UnsupportedMediaTypeError
from app.adapters.sky_is_no_limit_adapter import SkyIsNoLimitAdapter
from app.adapters.space_is_no_limit_adapter import SpaceIsNoLimitAdapter
from app.repository.stac_repository import upsert

adapters = [SkyIsNoLimitAdapter(), SpaceIsNoLimitAdapter()]


def upsert_stac_item(data: bytes, media_type: str) -> bool:
    stac_item = get_stac_item(data, media_type)
    return upsert(stac_item)


def get_stac_item(data: bytes, media_type: str) -> Item:
    candidates = [adapter for adapter in adapters if media_type in adapter.media_types]
    if not candidates:
        raise UnsupportedMediaTypeError(f"Unsupported media type: {media_type}")
    for adapter in candidates:
        if adapter.matches(data):
            return adapter.to_stac_item(data)
    raise UnsupportedFormatError("Unsupported payload format")
