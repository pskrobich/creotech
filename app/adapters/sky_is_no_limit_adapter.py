import json
from datetime import datetime

from pystac import Item, Asset, MediaType

from app.adapters.base_adapter import BaseAdapter, EO_EXT, PROCESSING_EXT


class SkyIsNoLimitAdapter(BaseAdapter):
    media_types = frozenset({"application/json"})

    def matches(self, payload: bytes) -> bool:
        try:
            document = json.loads(payload)
        except ValueError:
            return False
        return (
                isinstance(document, dict)
                and isinstance(document.get("acquisition_metadata"), dict)
                and document["acquisition_metadata"].get("provider_id") == "SkyIsNoLimit"
        )

    def _convert(self, payload: bytes) -> Item:
        document = json.loads(payload)
        acquisition_metadata = document["acquisition_metadata"]
        data_deliverables = document["data_deliverables"]
        product_characteristics = document["product_characteristics"]
        spatial_extent = document["spatial_extent"]
        bounding_box = spatial_extent["bounding_box"]

        return Item(
            id=acquisition_metadata["scene_identifier"],
            geometry=spatial_extent["geometry_geojson"],
            bbox=[
                bounding_box["min_longitude"],
                bounding_box["min_latitude"],
                bounding_box["max_longitude"],
                bounding_box["max_latitude"]
            ],
            datetime=datetime.fromisoformat(acquisition_metadata["capture_timestamp_utc"]),
            properties={
                "platform": acquisition_metadata["satellite_id"],
                "eo:cloud_cover": product_characteristics["metrics"]["cloud_cover_percentage"],
                "processing:level": product_characteristics["processing_level"]
            },
            stac_extensions=[EO_EXT, PROCESSING_EXT],
            collection=acquisition_metadata["mission_name"],
            assets={
                band: Asset(href=href, media_type=MediaType.GEOTIFF, roles=["data"])
                for band, href in data_deliverables["image_bands"].items()
            }
        )
