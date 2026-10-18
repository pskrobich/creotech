import pytest
from pyproj.exceptions import CRSError
from pystac.errors import STACValidationError
from shapely.errors import GEOSException

from app.adapters.space_is_no_limit_adapter import SpaceIsNoLimitAdapter
from tests.conftest import EXPECTED_SPACE_EYE_ITEM, apply, as_json, replace, with_text, without

adapter = SpaceIsNoLimitAdapter()


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
        item = adapter.to_stac_item(space_payload)

        assert as_json(item.to_dict()) == EXPECTED_SPACE_EYE_ITEM

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
