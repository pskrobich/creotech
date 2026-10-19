import pytest

from app.main import SEARCH_REQUEST_URL
from tests.api.conftest import JSON, XML, client, put_ingest
from tests.conftest import EXPECTED_SKY_SHIELD_ITEM, EXPECTED_SPACE_EYE_ITEM

SKY_SHIELD_ID = EXPECTED_SKY_SHIELD_ITEM["id"]
SPACE_EYE_ID = EXPECTED_SPACE_EYE_ITEM["id"]


@pytest.fixture(autouse=True)
def catalog(sky_payload, space_payload):
    put_ingest(sky_payload, JSON)
    put_ingest(space_payload, XML)


def get_search(**params):
    return client.get(SEARCH_REQUEST_URL, params=params)


def found_ids(response) -> list[str]:
    return [item["id"] for item in response.json()]


class TestSearch:

    @pytest.mark.parametrize(
        ("params", "expected_ids"),
        [
            pytest.param({}, [SPACE_EYE_ID, SKY_SHIELD_ID], id="no_filters_newest_first"),
            pytest.param({"limit": 1}, [SPACE_EYE_ID], id="first_page"),
            pytest.param({"limit": 1, "offset": 1}, [SKY_SHIELD_ID], id="second_page"),
            pytest.param({"limit": 1, "offset": 2}, [], id="page_after_last"),
            pytest.param({"max_cloud_coverage": 10}, [SPACE_EYE_ID], id="cloud_cover_below_sky_shield"),
            pytest.param({"max_cloud_coverage": 14.2}, [SPACE_EYE_ID, SKY_SHIELD_ID], id="cloud_cover_limit_inclusive"),
            pytest.param({"max_cloud_coverage": 100}, [SPACE_EYE_ID, SKY_SHIELD_ID], id="cloud_cover_hundred"),
            pytest.param({"max_cloud_coverage": 0}, [], id="cloud_cover_zero"),
            pytest.param({"max_cloud_coverage": 1}, [], id="cloud_cover_matches_nothing"),
            pytest.param({"processing_level": "L1C"}, [SKY_SHIELD_ID], id="level_l1c"),
            pytest.param({"processing_level": "L2A"}, [SPACE_EYE_ID], id="level_l2a"),
            pytest.param({"bbox": "21.0,52.36,21.2,52.39"}, [SKY_SHIELD_ID], id="bbox_north_of_space_eye"),
            pytest.param({"bbox": "20.0,52.0,20.95,52.3"}, [SKY_SHIELD_ID], id="bbox_west_of_space_eye"),
            pytest.param({"bbox": "21.0,51.4,21.2,52.1"}, [SPACE_EYE_ID], id="bbox_south_of_sky_shield"),
            pytest.param({"bbox": "22.0,51.5,22.5,52.0"}, [SPACE_EYE_ID], id="bbox_east_of_sky_shield"),
            pytest.param({"bbox": "21.0,52.2,21.2,52.3"}, [SPACE_EYE_ID, SKY_SHIELD_ID], id="bbox_where_footprints_overlap"),
            pytest.param({"bbox": "0,0,1,1"}, [], id="bbox_far_away"),
            pytest.param({"start_datetime": "2026-08-24T10:00:00Z"}, [SPACE_EYE_ID], id="datetime_only_start"),
            pytest.param(
                {"start_datetime": "2026-08-24T09:00:00Z", "end_datetime": "2026-08-24T10:00:00Z"},
                [SKY_SHIELD_ID],
                id="datetime_range_before_10",
            ),
            pytest.param(
                {"start_datetime": "2026-08-24T10:45:10Z", "end_datetime": "2026-08-24T10:45:10Z"},
                [SPACE_EYE_ID],
                id="datetime_instant_inside_acquisition_window",
            ),
            pytest.param({"end_datetime": "2026-08-23T00:00:00Z"}, [], id="datetime_open_range_before_all"),
            pytest.param(
                {"bbox": "20,51,23,53", "max_cloud_coverage": 10, "processing_level": "L2A"},
                [SPACE_EYE_ID],
                id="bbox_cloud_cover_and_level",
            ),
        ],
    )
    def test_filters_should_return_matching_items(self, params, expected_ids):
        response = get_search(**params)

        assert response.status_code == 200
        assert found_ids(response) == expected_ids

    @pytest.mark.parametrize(
        "params",
        [
            pytest.param({"bbox": "20,51,22"}, id="bbox_with_3_values"),
            pytest.param({"bbox": "abc,51,22,53"}, id="bbox_not_a_number"),
            pytest.param({"bbox": "20,91,22,53"}, id="bbox_latitude_out_of_range"),
            pytest.param({"bbox": "200,51,22,53"}, id="bbox_longitude_out_of_range"),
            pytest.param({"bbox": "20,53,22,51"}, id="bbox_miny_gt_maxy"),
            pytest.param({"bbox": "22,51,20,53"}, id="bbox_minx_gt_maxx"),
            pytest.param({"max_cloud_coverage": 101}, id="cloud_cover_above_100"),
            pytest.param({"max_cloud_coverage": -1}, id="cloud_cover_below_0"),
            pytest.param({"processing_level": ""}, id="empty_processing_level"),
            pytest.param({"start_datetime": "2026-08-24T10:00:00"}, id="datetime_without_timezone"),
            pytest.param(
                {"start_datetime": "2026-08-25T00:00:00Z", "end_datetime": "2026-08-24T00:00:00Z"},
                id="start_after_end",
            ),
            pytest.param({"limit": 0}, id="limit_zero"),
            pytest.param({"limit": 1001}, id="limit_above_1000"),
            pytest.param({"offset": -1}, id="offset_below_0"),
        ],
    )
    def test_invalid_parameters_should_return_422(self, params):
        response = get_search(**params)

        assert response.status_code == 422
