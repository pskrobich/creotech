import pytest
from pystac.errors import STACValidationError

from app.adapters.sky_is_no_limit_adapter import SkyIsNoLimitAdapter
from tests.conftest import EXPECTED_SKY_SHIELD_ITEM, as_json, edit_json

adapter = SkyIsNoLimitAdapter()


class TestMatches:

    def test_matches_sky_is_no_limit_json(self, sky_payload):
        assert adapter.matches(sky_payload)

    def test_does_not_match_space_is_no_limit_xml(self, space_payload):
        assert not adapter.matches(space_payload)

    def test_does_not_match_other_provider(self, sky_payload):
        payload = edit_json(sky_payload, lambda d: d["acquisition_metadata"].update(provider_id="Other"))
        assert not adapter.matches(payload)

    @pytest.mark.parametrize("payload", [
        b"",
        b"not json",
        b"[]", b"{}",
        b'{"acquisition_metadata": null}'
    ])
    def test_does_not_match_unrelated_payload(self, payload):
        assert not adapter.matches(payload)


class TestToStacItem:

    def test_converts_sample_to_stac_item(self, sky_payload):
        item = adapter.to_stac_item(sky_payload)

        assert as_json(item.to_dict()) == EXPECTED_SKY_SHIELD_ITEM

    @pytest.mark.parametrize(
        ("edit", "error"),
        [
            pytest.param(
                lambda d: d.pop("acquisition_metadata"),
                KeyError,
                id="no_acquisition_metadata",
            ),
            pytest.param(
                lambda d: d["acquisition_metadata"].pop("scene_identifier"),
                KeyError,
                id="no_scene_id",
            ),
            pytest.param(
                lambda d: d["product_characteristics"].pop("processing_level"),
                KeyError,
                id="no_level",
            ),
            pytest.param(
                lambda d: d["product_characteristics"]["metrics"].pop("cloud_cover_percentage"),
                KeyError,
                id="no_cloud_cover",
            ),
            pytest.param(
                lambda d: d["data_deliverables"].pop("image_bands"),
                KeyError,
                id="no_image_bands",
            ),
            pytest.param(
                lambda d: d["acquisition_metadata"].update(capture_timestamp_utc="yesterday"),
                ValueError,
                id="invalid_timestamp",
            ),
            pytest.param(
                lambda d: d["product_characteristics"]["metrics"].update(cloud_cover_percentage=150),
                STACValidationError,
                id="cloud_cover_above_100",
            ),
            pytest.param(
                lambda d: d["product_characteristics"]["metrics"].update(cloud_cover_percentage=-1),
                STACValidationError,
                id="cloud_cover_below_0",
            ),
            pytest.param(
                lambda d: d["product_characteristics"]["metrics"].update(cloud_cover_percentage="abc"),
                STACValidationError,
                id="cloud_cover_not_a_number",
            ),
            pytest.param(
                lambda d: d["product_characteristics"]["metrics"].update(cloud_cover_percentage=None),
                STACValidationError,
                id="cloud_cover_null",
            ),
            pytest.param(
                lambda d: d["acquisition_metadata"].update(scene_identifier=""),
                STACValidationError,
                id="empty_id",
            ),
            pytest.param(
                lambda d: d["acquisition_metadata"].update(scene_identifier=None),
                STACValidationError,
                id="null_id",
            ),
            pytest.param(
                lambda d: d["acquisition_metadata"].update(mission_name=""),
                STACValidationError,
                id="empty_collection",
            ),
            pytest.param(
                lambda d: d["product_characteristics"].update(processing_level=None),
                STACValidationError,
                id="null_level",
            ),
            pytest.param(
                lambda d: d["product_characteristics"]["metrics"].update(cloud_cover_percentage="14.2"),
                STACValidationError,
                id="cloud_cover_as_string",
            ),
            pytest.param(
                lambda d: d["spatial_extent"]["bounding_box"].update(min_longitude=None),
                STACValidationError,
                id="null_bbox_value",
            ),
            pytest.param(
                lambda d: d["spatial_extent"]["geometry_geojson"].pop("coordinates"),
                STACValidationError,
                id="geometry_without_coordinates",
            ),
            pytest.param(
                lambda d: d["data_deliverables"]["image_bands"].update(red=""),
                STACValidationError,
                id="empty_asset_href",
            ),
        ],
    )
    def test_invalid_metadata_raises(self, sky_payload, edit, error):
        with pytest.raises(error):
            adapter.to_stac_item(edit_json(sky_payload, edit))

    @pytest.mark.parametrize(
        "edit",
        [
            pytest.param(lambda d: d["product_characteristics"].update(processing_level=""), id="empty_level"),
            pytest.param(lambda d: d["data_deliverables"].update(image_bands={}), id="no_assets"),
            pytest.param(lambda d: d["spatial_extent"].update(geometry_geojson=None), id="no_geometry"),
            pytest.param(
                lambda d: d["acquisition_metadata"].update(capture_timestamp_utc="2026-08-24T09:15:22"),
                id="timestamp_without_timezone",
            ),
        ],
    )
    def test_data_quality_issues_are_accepted(self, sky_payload, edit):
        assert adapter.to_stac_item(edit_json(sky_payload, edit))
