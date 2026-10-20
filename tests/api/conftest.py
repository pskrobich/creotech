import pytest
from fastapi.testclient import TestClient

from app.database import pool
from app.api.stac_api import INGEST_REQUEST_URL, SEARCH_REQUEST_URL, V1_REQUEST_MAPPING
from app.main import app

client = TestClient(app)

JSON = "application/json"
XML = "application/xml"


@pytest.fixture(scope="session", autouse=True)
def running_app():
    with client:
        yield


@pytest.fixture(autouse=True)
def empty_table(running_app):
    with pool.connection() as conn:
        conn.execute("TRUNCATE stac_items")


def put_ingest(payload: bytes, media_type: str | None):
    headers = {"Content-Type": media_type} if media_type is not None else {}
    return client.put(f"{V1_REQUEST_MAPPING}{INGEST_REQUEST_URL}", content=payload, headers=headers)


def get_search(**params):
    return client.get(f"{V1_REQUEST_MAPPING}{SEARCH_REQUEST_URL}", params=params)
