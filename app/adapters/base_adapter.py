from abc import ABC, abstractmethod
from typing import ClassVar

from pystac import Item, Link, MediaType, RelType

EO_EXT = "https://stac-extensions.github.io/eo/v2.0.0/schema.json"
PROCESSING_EXT = "https://stac-extensions.github.io/processing/v1.2.0/schema.json"


class BaseAdapter(ABC):
    media_types: ClassVar[frozenset[str]]

    @abstractmethod
    def matches(self, payload: bytes) -> bool:
        """Returns True if the payload is in this provider's format."""

    @abstractmethod
    def convert(self, payload: bytes) -> Item:
        """Maps the provider's raw metadata to a STAC Item, without validating it."""

    def to_stac_item(self, payload: bytes) -> Item:
        item = self.convert(payload)
        item.add_link(Link(RelType.COLLECTION, f"../../{item.collection_id}", media_type=MediaType.JSON))
        item.validate()
        return item
