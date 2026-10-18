import re

import pytest
from pyproj.exceptions import CRSError
from pystac.errors import STACValidationError
from shapely.errors import GEOSException

from app.adapters.base_adapter import EO_EXT, PROCESSING_EXT
from app.adapters.space_is_no_limit_adapter import SpaceIsNoLimitAdapter

adapter = SpaceIsNoLimitAdapter()


def with_text(tag: str, value: str):
    pattern = rf"<{tag}>.*?</{tag}>".encode()

    def edit(payload: bytes) -> bytes:
        assert re.search(pattern, payload, flags=re.S), f"<{tag}> not found in the sample"
        return re.sub(pattern, f"<{tag}>{value}</{tag}>".encode(), payload, count=1, flags=re.S)

    return edit


def without(tag: str):
    pattern = rf"<{tag}(\s[^>]*)?>.*?</{tag}>\s*".encode()

    def edit(payload: bytes) -> bytes:
        assert re.search(pattern, payload, flags=re.S), f"<{tag}> not found in the sample"
        return re.sub(pattern, b"", payload, flags=re.S)

    return edit


def replace(old: bytes, new: bytes):
    """Raw byte replacement, for edits that are not about a single element (namespace, DOCTYPE)."""

    def edit(payload: bytes) -> bytes:
        assert old in payload, f"{old!r} not found in the sample"
        return payload.replace(old, new)

    return edit


def apply(payload: bytes, *edits) -> bytes:
    for edit in edits:
        payload = edit(payload)
    return payload


class TestMatches:

    def test_matches_space_is_no_limit_xml(self, space_payload):
        assert adapter.matches(space_payload)

    def test_does_not_match_sky_is_no_limit_json(self, sky_payload):
        assert not adapter.matches(sky_payload)

    def test_does_not_match_other_provider(self, space_payload):
        assert not adapter.matches(apply(space_payload, with_text("Provider", "Other")))

    def test_does_not_match_xml_without_namespace(self, space_payload):
        payload = apply(space_payload, replace(b' xmlns="http://spaceisnolimit.com/schemas/metadata/v2"', b""))
        assert not adapter.matches(payload)

    def test_does_not_match_xml_with_entities(self, space_payload):
        doctype = b'<!DOCTYPE g [<!ENTITY x SYSTEM "file:///etc/passwd">]>\n<GranuleMetadata'
        assert not adapter.matches(apply(space_payload, replace(b"<GranuleMetadata", doctype)))

    @pytest.mark.parametrize("payload", [
        b"",
        b"not xml",
        b"<GranuleMetadata>",
        b"<root/>",
        b"{}",
    ])
    def test_does_not_match_unrelated_payload(self, payload):
        assert not adapter.matches(payload)


class TestToStacItem:

    def test_converts_sample_to_stac_item(self, space_payload):
        item_dict = adapter.to_stac_item(space_payload).to_dict()

        geometry = item_dict.pop("geometry")
        bbox = item_dict.pop("bbox")
        assert geometry["type"] == "Polygon"
        coordinates = [[list(point) for point in ring] for ring in geometry["coordinates"]]
        assert coordinates == [[
            pytest.approx(point, abs=1e-6)
            for point in [
                [21.0, 52.350293],
                [21.0, 51.363242],
                [22.576519, 51.352634],
                [22.611378, 52.339305],
                [21.0, 52.350293],
            ]
        ]]
        assert bbox == pytest.approx([21.0, 51.352634, 22.611378, 52.350293], abs=1e-6)

        assert item_dict == {
            "type": "Feature",
            "stac_version": "1.1.0",
            "stac_extensions": [EO_EXT, PROCESSING_EXT],
            "id": "SE02_L2A_20260824T104500_N001",
            "collection": "SPACE_EYE",
            "properties": {
                "datetime": "2026-08-24T10:45:00Z",
                "start_datetime": "2026-08-24T10:45:00Z",
                "end_datetime": "2026-08-24T10:45:18Z",
                "platform": "SE-02",
                "eo:cloud_cover": 4.85,
                "processing:level": "L2A",
            },
            "assets": {
                band: {
                    "href": f"s3://space-eye-products/2026/L2A/SE02_20260824_{file}.tif",
                    "type": "image/tiff; application=geotiff",
                    "roles": ["data"],
                }
                for band, file in [("red", "B04"), ("nir", "B08")]
            },
            "links": [{"rel": "collection", "href": "../../SPACE_EYE", "type": "application/json"}],
        }

    @pytest.mark.parametrize("tag", [
        "HeaderInfo",
        "GranuleID",
        "SpacecraftID",
        "Mission",
        "TemporalCoverage",
        "StartTimeUTC",
        "StopTimeUTC",
        "ProductQuality",
        "ProcessingLevel",
        "CloudCoveragePercentage",
        "GeometricProperties",
        "CRS",
        "FootprintWKT",
        "RasterFiles",
        "URL",
    ])
    def test_missing_element_raises(self, space_payload, tag):
        with pytest.raises(ValueError, match=f"g:{tag}"):
            adapter.to_stac_item(apply(space_payload, without(tag)))

    @pytest.mark.parametrize("tag", [
        "GranuleID",
        "SpacecraftID",
        "Mission",
        "StartTimeUTC",
        "ProcessingLevel",
        "CloudCoveragePercentage",
        "CRS",
        "FootprintWKT",
        "URL",
    ])
    def test_empty_element_raises(self, space_payload, tag):
        with pytest.raises(ValueError, match=f"g:{tag}"):
            adapter.to_stac_item(apply(space_payload, with_text(tag, "")))

    @pytest.mark.parametrize(
        ("tag", "value", "error"),
        [
            pytest.param("CloudCoveragePercentage", "abc", ValueError, id="cloud_cover_not_a_number"),
            pytest.param("CloudCoveragePercentage", "4,85", ValueError, id="cloud_cover_with_decimal_comma"),
            pytest.param("CloudCoveragePercentage", "150", STACValidationError, id="cloud_cover_above_100"),
            pytest.param("CloudCoveragePercentage", "-1", STACValidationError, id="cloud_cover_below_0"),
            pytest.param("StartTimeUTC", "yesterday", ValueError, id="invalid_timestamp"),
            pytest.param("FootprintWKT", "POINT(500000 5800000)", ValueError, id="footprint_not_a_polygon"),
            pytest.param("FootprintWKT", "POLYGON EMPTY", ValueError, id="empty_footprint"),
            pytest.param("FootprintWKT", "POLYGON((500000 5800000", GEOSException, id="malformed_footprint"),
            pytest.param("CRS", "EPSG:999999", CRSError, id="unknown_crs"),
        ],
    )
    def test_invalid_value_raises(self, space_payload, tag, value, error):
        with pytest.raises(error):
            adapter.to_stac_item(apply(space_payload, with_text(tag, value)))

    @pytest.mark.parametrize(
        "edits",
        [
            pytest.param([without("Band")], id="no_assets"),
            pytest.param([with_text("StopTimeUTC", "2026-08-24T10:44:00Z")], id="stop_before_start"),
            pytest.param(
                [
                    with_text("StartTimeUTC", "2026-08-24T10:45:00"),
                    with_text("StopTimeUTC", "2026-08-24T10:45:18"),
                ],
                id="timestamps_without_timezone",
            ),
        ],
    )
    def test_data_quality_issues_are_accepted(self, space_payload, edits):
        assert adapter.to_stac_item(apply(space_payload, *edits))
