from datetime import UTC, datetime
from unittest.mock import ANY

import pytest
from psycopg.rows import dict_row

from app.database import pool
from tests.api.conftest import JSON, XML, count_stored_items, put_ingest
from tests.conftest import (
    EXPECTED_SKY_SHIELD_ITEM,
    EXPECTED_SPACE_EYE_ITEM,
    apply,
    edit_json,
    with_text,
    without,
)

EXPECTED_SKY_SHIELD_ROW = {
    "collection": "SKY_SHIELD",
    "id": "SKY_SHIELD_20260824_091522_L1C_POL",
    "item": EXPECTED_SKY_SHIELD_ITEM,
    "geometry": ANY,
    "geometry_geojson": EXPECTED_SKY_SHIELD_ITEM["geometry"],
    "start_datetime": datetime(2026, 8, 24, 9, 15, 22, 451000, tzinfo=UTC),
    "end_datetime": datetime(2026, 8, 24, 9, 15, 22, 451000, tzinfo=UTC),
    "cloud_cover": 14.2,
    "processing_level": "L1C",
    "created_at": ANY,
    "updated_at": ANY,
}
EXPECTED_SPACE_EYE_ROW = {
    "collection": "SPACE_EYE",
    "id": "SE02_L2A_20260824T104500_N001",
    "item": EXPECTED_SPACE_EYE_ITEM,
    "geometry": ANY,
    "geometry_geojson": EXPECTED_SPACE_EYE_ITEM["geometry"],
    "start_datetime": datetime(2026, 8, 24, 10, 45, 0, tzinfo=UTC),
    "end_datetime": datetime(2026, 8, 24, 10, 45, 18, tzinfo=UTC),
    "cloud_cover": 4.85,
    "processing_level": "L2A",
    "created_at": ANY,
    "updated_at": ANY,
}


def fetch_stored_item(collection: str, item_id: str) -> dict | None:
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            """
            SELECT *, ST_AsGeoJSON(geometry) ::jsonb AS geometry_geojson
            FROM stac_items
            WHERE collection = %s
              AND id = %s
            """,
            (collection, item_id),
        ).fetchone()


def unchanged(payload: bytes) -> bytes:
    return payload


def replaced_by(content: bytes):
    return lambda payload: content


class TestIngest:

    @pytest.mark.parametrize(
        ("fixture", "media_type", "expected_row"),
        [
            pytest.param(
                "sky_payload",
                JSON,
                EXPECTED_SKY_SHIELD_ROW,
                id="sky_is_no_limit_json"
            ),
            pytest.param(
                "sky_payload",
                "Application/JSON",
                EXPECTED_SKY_SHIELD_ROW,
                id="json_uppercase"
            ),
            pytest.param(
                "sky_payload",
                "application/json; charset=utf-8",
                EXPECTED_SKY_SHIELD_ROW,
                id="json_with_charset"
            ),
            pytest.param(
                "space_payload",
                XML,
                EXPECTED_SPACE_EYE_ROW,
                id="space_is_no_limit_xml"
            ),
            pytest.param(
                "space_payload",
                "text/xml",
                EXPECTED_SPACE_EYE_ROW,
                id="xml_as_text_xml"
            ),
            pytest.param(
                "space_payload",
                "application/xml; charset=utf-8",
                EXPECTED_SPACE_EYE_ROW,
                id="xml_with_charset"
            ),
        ],
    )
    def test_ingests_provider_sample_should_return_201_and_store_item(
            self, request, fixture, media_type, expected_row
    ):
        response = put_ingest(request.getfixturevalue(fixture), media_type)

        assert response.status_code == 201
        assert response.content == b""
        assert fetch_stored_item(expected_row["collection"], expected_row["id"]) == expected_row

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
        assert count_stored_items() == 3
        assert fetch_stored_item("SKY_SHIELD", EXPECTED_SKY_SHIELD_ROW["id"]) == EXPECTED_SKY_SHIELD_ROW
        assert fetch_stored_item("SKY_SHIELD", other_sky_id) == {
            **EXPECTED_SKY_SHIELD_ROW,
            "id": other_sky_id,
            "item": {**EXPECTED_SKY_SHIELD_ITEM, "id": other_sky_id},
        }
        assert fetch_stored_item("SPACE_EYE", EXPECTED_SPACE_EYE_ROW["id"]) == EXPECTED_SPACE_EYE_ROW

    @pytest.mark.parametrize(
        ("fixture", "media_type", "edit", "expected_row"),
        [
            pytest.param("sky_payload", JSON, unchanged, EXPECTED_SKY_SHIELD_ROW, id="identical_json"),
            pytest.param("space_payload", XML, unchanged, EXPECTED_SPACE_EYE_ROW, id="identical_xml"),
            pytest.param(
                "sky_payload",
                JSON,
                lambda p: edit_json(p, lambda d: d["product_characteristics"]["metrics"].update(
                    cloud_cover_percentage=3.5)),
                {
                    **EXPECTED_SKY_SHIELD_ROW,
                    "item": {
                        **EXPECTED_SKY_SHIELD_ITEM,
                        "properties": {**EXPECTED_SKY_SHIELD_ITEM["properties"], "eo:cloud_cover": 3.5},
                    },
                    "cloud_cover": 3.5,
                },
                id="changed_json",
            ),
            pytest.param(
                "space_payload",
                XML,
                with_text("CloudCoveragePercentage", "3.5"),
                {
                    **EXPECTED_SPACE_EYE_ROW,
                    "item": {
                        **EXPECTED_SPACE_EYE_ITEM,
                        "properties": {**EXPECTED_SPACE_EYE_ITEM["properties"], "eo:cloud_cover": 3.5},
                    },
                    "cloud_cover": 3.5,
                },
                id="changed_xml",
            ),
        ],
    )
    def test_reingesting_should_return_204_and_replace_item(
            self, request, fixture, media_type, edit, expected_row
    ):
        payload = request.getfixturevalue(fixture)
        put_ingest(payload, media_type)
        first_save = fetch_stored_item(expected_row["collection"], expected_row["id"])

        response = put_ingest(apply(payload, edit), media_type)

        assert response.status_code == 204
        assert response.content == b""
        assert count_stored_items() == 1
        stored = fetch_stored_item(expected_row["collection"], expected_row["id"])
        assert stored == expected_row
        assert stored["created_at"] == first_save["created_at"]
        assert stored["updated_at"] > first_save["updated_at"]

    @pytest.mark.parametrize(
        ("fixture", "media_type", "edit", "reason", "expected_row"),
        [
            pytest.param(
                "sky_payload",
                JSON,
                lambda p: edit_json(p, lambda d: d["product_characteristics"]["metrics"].update(
                    cloud_cover_percentage=101)),
                "101 is greater than the maximum of 100",
                EXPECTED_SKY_SHIELD_ROW,
                id="sky_is_no_limit_json",
            ),
            pytest.param(
                "space_payload",
                XML,
                with_text("CloudCoveragePercentage", "101"),
                "101.0 is greater than the maximum of 100",
                EXPECTED_SPACE_EYE_ROW,
                id="space_is_no_limit_xml",
            ),
        ],
    )
    def test_reingesting_invalid_metadata_should_return_422_and_keep_stored_item(
            self, request, fixture, media_type, edit, reason, expected_row
    ):
        payload = request.getfixturevalue(fixture)
        put_ingest(payload, media_type)
        first_save = fetch_stored_item(expected_row["collection"], expected_row["id"])

        response = put_ingest(apply(payload, edit), media_type)

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail.startswith("Invalid metadata:")
        assert reason in detail
        assert count_stored_items() == 1
        stored = fetch_stored_item(expected_row["collection"], expected_row["id"])
        assert stored == expected_row
        assert stored == first_save

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
        assert count_stored_items() == 0

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
        assert count_stored_items() == 0

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
        assert count_stored_items() == 0