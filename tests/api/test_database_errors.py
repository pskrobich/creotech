import pytest
from psycopg import OperationalError
from psycopg_pool import PoolTimeout

from tests.api.conftest import JSON, get_search, put_ingest

DATABASE_UNAVAILABLE = {"detail": "Database is temporarily unavailable"}


def failing_database(error: Exception):

    def fail(*args, **kwargs):
        raise error

    return fail


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(OperationalError("connection refused"), id="connection_lost"),
        pytest.param(PoolTimeout("couldn't get a connection after 30.00 sec"), id="no_free_connection"),
    ],
)
class TestDatabaseUnavailable:

    def test_ingest_should_return_503(self, monkeypatch, sky_payload, error):
        monkeypatch.setattr("app.service.stac_service.upsert", failing_database(error))

        response = put_ingest(sky_payload, JSON)

        assert response.status_code == 503
        assert response.json() == DATABASE_UNAVAILABLE

    def test_search_should_return_503(self, monkeypatch, error):
        monkeypatch.setattr("app.service.stac_service.find_items", failing_database(error))

        response = get_search()

        assert response.status_code == 503
        assert response.json() == DATABASE_UNAVAILABLE
