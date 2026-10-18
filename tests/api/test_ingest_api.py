import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import (
    EXPECTED_SKY_SHIELD_ITEM,
    EXPECTED_SPACE_EYE_ITEM,
    apply,
    edit_json,
    with_text,
    without,
)

client = TestClient(app)

JSON = "application/json"
XML = "application/xml"


def post_ingest(payload: bytes, media_type: str | None):
    headers = {"Content-Type": media_type} if media_type is not None else {}
    return client.post("/ingest", content=payload, headers=headers)


class TestIngest:

    @pytest.mark.parametrize(
        ("fixture", "media_type", "expected_item"),
        [
            pytest.param("sky_payload", JSON, EXPECTED_SKY_SHIELD_ITEM, id="sky_is_no_limit_json"),
            pytest.param("sky_payload", "Application/JSON", EXPECTED_SKY_SHIELD_ITEM, id="json_uppercase"),
            pytest.param("sky_payload", "application/json; charset=utf-8", EXPECTED_SKY_SHIELD_ITEM,
                         id="json_with_charset"),
            pytest.param("space_payload", XML, EXPECTED_SPACE_EYE_ITEM, id="space_is_no_limit_xml"),
            pytest.param("space_payload", "text/xml", EXPECTED_SPACE_EYE_ITEM, id="xml_as_text_xml"),
            pytest.param("space_payload", "application/xml; charset=utf-8", EXPECTED_SPACE_EYE_ITEM,
                         id="xml_with_charset"),
        ],
    )
    def test_ingests_provider_sample_should_return_201(self, request, fixture, media_type, expected_item):
        response = post_ingest(request.getfixturevalue(fixture), media_type)

        assert response.status_code == 201
        assert response.json() == expected_item

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
        response = post_ingest(sky_payload, media_type)

        assert response.status_code == 415
        assert response.json()["detail"].startswith("Unsupported media type")

    @pytest.mark.parametrize(
        ("fixture", "media_type"),
        [
            pytest.param("sky_payload", XML, id="json_sent_as_xml"),
            pytest.param("space_payload", JSON, id="xml_sent_as_json"),
        ],
    )
    def test_payload_not_matching_media_type_should_return_400(self, request, fixture, media_type):
        response = post_ingest(request.getfixturevalue(fixture), media_type)

        assert response.status_code == 400
        assert response.json() == {"detail": "Unsupported payload format"}

    @pytest.mark.parametrize(
        ("payload", "media_type"),
        [
            pytest.param(b"", JSON, id="empty_json"),
            pytest.param(b"not json", JSON, id="not_json"),
            pytest.param(b"{}", JSON, id="empty_object"),
            pytest.param(b"", XML, id="empty_xml"),
            pytest.param(b"not xml", XML, id="not_xml"),
            pytest.param(b"<root/>", XML, id="unknown_root"),
        ],
    )
    def test_unsupported_format_should_return_400(self, payload, media_type):
        response = post_ingest(payload, media_type)

        assert response.status_code == 400
        assert response.json() == {"detail": "Unsupported payload format"}

    @pytest.mark.parametrize(
        ("fixture", "media_type", "edit"),
        [
            pytest.param(
                "sky_payload",
                JSON,
                lambda p: edit_json(p, lambda d: d["acquisition_metadata"].update(provider_id="Other")),
                id="other_json_provider",
            ),
            pytest.param("space_payload", XML, with_text("Provider", "Other"), id="other_xml_provider"),
        ],
    )
    def test_other_provider_should_return_400(self, request, fixture, media_type, edit):
        response = post_ingest(apply(request.getfixturevalue(fixture), edit), media_type)

        assert response.status_code == 400
        assert response.json() == {"detail": "Unsupported payload format"}

    def test_truncated_xml_should_return_400(self, space_payload):
        response = post_ingest(space_payload[:-30], XML)

        assert response.status_code == 400
        assert response.json() == {"detail": "Unsupported payload format"}

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
        response = post_ingest(apply(request.getfixturevalue(fixture), edit), media_type)

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail.startswith("Invalid metadata:")
        assert reason in detail
