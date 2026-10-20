from datetime import datetime
from xml.etree.ElementTree import Element, ParseError

import numpy as np
import shapely
from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring
from pyproj import Transformer
from pystac import Asset, Item, MediaType
from shapely.geometry import Polygon, mapping
from shapely.geometry.polygon import orient

from app.adapters.base_adapter import EO_EXT, PROCESSING_EXT, BaseAdapter

NS = {"g": "http://spaceisnolimit.com/schemas/metadata/v2"}


class SpaceIsNoLimitAdapter(BaseAdapter):
    media_types = frozenset({"application/xml", "text/xml"})

    def matches(self, payload: bytes) -> bool:
        try:
            root = fromstring(payload)
        except (ParseError, DefusedXmlException):
            return False
        return root.findtext("g:HeaderInfo/g:Provider", namespaces=NS) == "SpaceIsNoLimit"

    def _convert(self, payload: bytes) -> Item:
        root = fromstring(payload)
        header_info = self._required_element(root, "g:HeaderInfo")
        temporal_coverage = self._required_element(root, "g:TemporalCoverage")
        product_quality = self._required_element(root, "g:ProductQuality")
        geometric_properties = self._required_element(root, "g:GeometricProperties")
        raster_files = self._required_element(root, "g:RasterFiles")

        footprint = shapely.from_wkt(self._required_text(geometric_properties, "g:FootprintWKT"))
        if not isinstance(footprint, Polygon):
            raise ValueError(f"Footprint must be a polygon, got {footprint.geom_type}")
        if footprint.is_empty:
            raise ValueError("Footprint must not be empty")
        to_wgs84 = Transformer.from_crs(
            self._required_text(geometric_properties, "g:CRS"), "EPSG:4326", always_xy=True
        )

        def to_lon_lat(coords: np.ndarray) -> np.ndarray:
            lon, lat = to_wgs84.transform(coords[:, 0], coords[:, 1])
            return np.round(np.column_stack([lon, lat]), 7)

        geometry = orient(shapely.transform(footprint, to_lon_lat))

        start = datetime.fromisoformat(self._required_text(temporal_coverage, "g:StartTimeUTC"))
        end = datetime.fromisoformat(self._required_text(temporal_coverage, "g:StopTimeUTC"))

        return Item(
            id=self._required_text(header_info, "g:GranuleID"),
            geometry=mapping(geometry),
            bbox=list(geometry.bounds),
            datetime=start,
            start_datetime=start,
            end_datetime=end,
            properties={
                "platform": self._required_text(header_info, "g:SpacecraftID"),
                "eo:cloud_cover": float(self._required_text(product_quality, "g:CloudCoveragePercentage")),
                "processing:level": self._required_text(product_quality, "g:ProcessingLevel"),
            },
            stac_extensions=[EO_EXT, PROCESSING_EXT],
            collection=self._required_text(header_info, "g:Mission"),
            assets={
                band.get("name", "").split("_")[-1].lower(): Asset(
                    href=self._required_text(band, "g:URL"),
                    media_type=MediaType.GEOTIFF,
                    roles=["data"],
                )
                for band in raster_files.iterfind("g:Band", NS)
            },
        )

    @staticmethod
    def _required_element(parent: Element, path: str) -> Element:
        element = parent.find(path, NS)
        if element is None:
            raise ValueError(f"Missing required element: {path}")
        return element

    @staticmethod
    def _required_text(parent: Element, path: str) -> str:
        text = parent.findtext(path, namespaces=NS)
        if text is None or not text.strip():
            raise ValueError(f"Missing required element: {path}")
        return text.strip()
