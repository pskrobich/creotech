import pytest

from tests.api.conftest import JSON, XML, get_search, put_ingest
from tests.conftest import (
    EXPECTED_SKY_SHIELD_ITEM,
    EXPECTED_SPACE_EYE_ITEM,
    apply,
    edit_json,
    with_text,
    without,
)


def get_stored_items() -> list[dict]:
    response = get_search()
    assert response.status_code == 200
    return response.json()


def unchanged(payload: bytes) -> bytes:
    return payload


def replaced_by(content: bytes):
    return lambda payload: content


class TestIngest:

    @pytest.mark.parametrize(
        ("fixture", "media_type", "expected_item"),
        [
            pytest.param(
                "sky_payload",
                JSON,
                EXPECTED_SKY_SHIELD_ITEM,
                id="sky_is_no_limit_json"
            ),
            pytest.param(
                "sky_payload",
                "Application/JSON",
                EXPECTED_SKY_SHIELD_ITEM,
                id="json_uppercase"
            ),
            pytest.param(
                "sky_payload",
                "application/json; charset=utf-8",
                EXPECTED_SKY_SHIELD_ITEM,
                id="json_with_charset"
            ),
            pytest.param(
                "space_payload",
                XML,
                EXPECTED_SPACE_EYE_ITEM,
                id="space_is_no_limit_xml"
            ),
            pytest.param(
                "space_payload",
                "text/xml",
                EXPECTED_SPACE_EYE_ITEM,
                id="xml_as_text_xml"
            ),
            pytest.param(
                "space_payload",
                "application/xml; charset=utf-8",
                EXPECTED_SPACE_EYE_ITEM,
                id="xml_with_charset"
            ),
        ],
    )
    def test_ingests_provider_sample_should_return_201_and_store_item(
            self, request, fixture, media_type, expected_item
    ):
        response = put_ingest(request.getfixturevalue(fixture), media_type)

        assert response.status_code == 201
        assert response.content == b""
        assert get_stored_items() == [expected_item]

    def test_ingesting_different_products_should_store_each_of_them(self, sky_payload, space_payload):
        other_sky_id = "SKY_SHIELD_20260825_101010_L1C_POL"
        other_sky_payload = edit_json(
            sky_payload, lambda d: d["acquisition_metadata"].update(scene_identifier=other_sky_id)
        )

        responses = [
            put_ingest(sky_payload, JSON),
            put_ingest(other_sky_payload, JSON),
            put_ingest(space_payload, XML),
        ]

        assert [response.status_code for response in responses] == [201, 201, 201]
        assert get_stored_items() == [
            EXPECTED_SPACE_EYE_ITEM,
            EXPECTED_SKY_SHIELD_ITEM,
            {**EXPECTED_SKY_SHIELD_ITEM, "id": other_sky_id},
        ]

    @pytest.mark.parametrize(
        ("fixture", "media_type", "edit", "expected_item"),
        [
            pytest.param("sky_payload", JSON, unchanged, EXPECTED_SKY_SHIELD_ITEM, id="identical_json"),
            pytest.param("space_payload", XML, unchanged, EXPECTED_SPACE_EYE_ITEM, id="identical_xml"),
            pytest.param(
                "sky_payload",
                JSON,
                lambda p: edit_json(p, lambda d: d["product_characteristics"]["metrics"].update(
                    cloud_cover_percentage=3.5)),
                {
                    **EXPECTED_SKY_SHIELD_ITEM,
                    "properties": {**EXPECTED_SKY_SHIELD_ITEM["properties"], "eo:cloud_cover": 3.5},
                },
                id="changed_json",
            ),
            pytest.param(
                "space_payload",
                XML,
                with_text("CloudCoveragePercentage", "3.5"),
                {
                    **EXPECTED_SPACE_EYE_ITEM,
                    "properties": {**EXPECTED_SPACE_EYE_ITEM["properties"], "eo:cloud_cover": 3.5},
                },
                id="changed_xml",
            ),
        ],
    )
    def test_reingesting_should_return_204_and_replace_item(
            self, request, fixture, media_type, edit, expected_item
    ):
        payload = request.getfixturevalue(fixture)
        put_ingest(payload, media_type)

        response = put_ingest(apply(payload, edit), media_type)

        assert response.status_code == 204
        assert response.content == b""
        assert get_stored_items() == [expected_item]

    @pytest.mark.parametrize(
        ("fixture", "media_type", "edit", "reason", "expected_item"),
        [
            pytest.param(
                "sky_payload",
                JSON,
                lambda p: edit_json(p, lambda d: d["product_characteristics"]["metrics"].update(
                    cloud_cover_percentage=101)),
                "101 is greater than the maximum of 100",
                EXPECTED_SKY_SHIELD_ITEM,
                id="sky_is_no_limit_json",
            ),
            pytest.param(
                "space_payload",
                XML,
                with_text("CloudCoveragePercentage", "101"),
                "101.0 is greater than the maximum of 100",
                EXPECTED_SPACE_EYE_ITEM,
                id="space_is_no_limit_xml",
            ),
        ],
    )
    def test_reingesting_invalid_metadata_should_return_422_and_keep_stored_item(
            self, request, fixture, media_type, edit, reason, expected_item
    ):
        payload = request.getfixturevalue(fixture)
        put_ingest(payload, media_type)

        response = put_ingest(apply(payload, edit), media_type)

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail.startswith("Invalid metadata:")
        assert reason in detail
        assert get_stored_items() == [expected_item]

    @pytest.mark.parametrize(
        "media_type",
        [
            pytest.param(None, id="no_content_type"),
            pytest.param("text/plain", id="text_plain"),
            pytest.param("application/x-www-form-urlencoded", id="curl_default"),
            pytest.param("application/octet-stream", id="octet_stream"),
        ],
    )
    def test_unsupported_media_type_should_return_415(self, sky_payload, media_type):
        response = put_ingest(sky_payload, media_type)

        assert response.status_code == 415
        assert response.json()["detail"].startswith("Unsupported media type")
        assert get_stored_items() == []

    @pytest.mark.parametrize(
        ("fixture", "media_type", "edit"),
        [
            pytest.param("sky_payload", XML, unchanged, id="json_sent_as_xml"),
            pytest.param("space_payload", JSON, unchanged, id="xml_sent_as_json"),
            pytest.param("sky_payload", JSON, replaced_by(b""), id="empty_json"),
            pytest.param("sky_payload", JSON, replaced_by(b"not json"), id="not_json"),
            pytest.param("sky_payload", JSON, replaced_by(b"{}"), id="empty_object"),
            pytest.param("space_payload", XML, replaced_by(b""), id="empty_xml"),
            pytest.param("space_payload", XML, replaced_by(b"not xml"), id="not_xml"),
            pytest.param("space_payload", XML, replaced_by(b"<root/>"), id="unknown_root"),
            pytest.param(
                "sky_payload",
                JSON,
                lambda p: edit_json(p, lambda d: d["acquisition_metadata"].update(provider_id="Other")),
                id="other_json_provider",
            ),
            pytest.param("space_payload", XML, with_text("Provider", "Other"), id="other_xml_provider"),
            pytest.param("space_payload", XML, lambda p: p[:-30], id="truncated_xml"),
        ],
    )
    def test_unrecognized_payload_should_return_400(self, request, fixture, media_type, edit):
        response = put_ingest(apply(request.getfixturevalue(fixture), edit), media_type)

        assert response.status_code == 400
        assert response.json() == {"detail": "Unsupported payload format"}
        assert get_stored_items() == []

    @pytest.mark.parametrize(
        ("fixture", "media_type", "edit", "reason"),
        [
            # One case per kind of adapter error; the adapter tests cover the edge cases
            pytest.param(
                "sky_payload",
                JSON,
                lambda p: edit_json(p, lambda d: d["acquisition_metadata"].pop("scene_identifier")),
                "scene_identifier",
                id="json_missing_field",
            ),
            pytest.param(
                "sky_payload",
                JSON,
                lambda p: edit_json(p, lambda d: d["acquisition_metadata"].update(capture_timestamp_utc="yesterday")),
                "yesterday",
                id="json_invalid_timestamp",
            ),
            pytest.param(
                "sky_payload",
                JSON,
                lambda p: edit_json(p, lambda d: d["product_characteristics"]["metrics"].update(
                    cloud_cover_percentage=150)),
                "150 is greater than the maximum of 100",
                id="json_cloud_cover_above_100",
            ),
            pytest.param("space_payload", XML, without("GranuleID"), "g:GranuleID", id="xml_missing_element"),
            pytest.param(
                "space_payload", XML, with_text("StartTimeUTC", "yesterday"), "yesterday", id="xml_invalid_timestamp"
            ),
            pytest.param(
                "space_payload",
                XML,
                with_text("CloudCoveragePercentage", "150"),
                "150.0 is greater than the maximum of 100",
                id="xml_cloud_cover_above_100",
            ),
            pytest.param(
                "space_payload",
                XML,
                with_text("FootprintWKT", "POLYGON((500000 5800000"),
                "ParseException",
                id="xml_malformed_footprint",
            ),
            pytest.param("space_payload", XML, with_text("CRS", "EPSG:999999"), "EPSG:999999", id="xml_unknown_crs"),
            pytest.param(
                "sky_payload",
                JSON,
                lambda p: edit_json(p, lambda d: d.update(product_characteristics=[])),
                "list indices must be integers",
                id="json_section_is_a_list",
            ),
            pytest.param(
                "sky_payload",
                JSON,
                lambda p: edit_json(p, lambda d: d["data_deliverables"].update(image_bands=[])),
                "has no attribute 'items'",
                id="json_image_bands_is_a_list",
            ),
            pytest.param(
                "sky_payload",
                JSON,
                lambda p: edit_json(p, lambda d: d["acquisition_metadata"].update(capture_timestamp_utc=None)),
                "argument must be str",
                id="json_null_timestamp",
            ),
        ],
    )
    def test_invalid_metadata_should_return_422(self, request, fixture, media_type, edit, reason):
        response = put_ingest(apply(request.getfixturevalue(fixture), edit), media_type)

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail.startswith("Invalid metadata:")
        assert reason in detail
        assert get_stored_items() == []