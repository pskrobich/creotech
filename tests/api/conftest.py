import pytest
from fastapi.testclient import TestClient

from app.database import pool
from app.main import INGEST_REQUEST_URL, app

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
    return client.put(INGEST_REQUEST_URL, content=payload, headers=headers)


def count_stored_items() -> int:
    with pool.connection() as conn:
        return conn.execute("SELECT count(*) FROM stac_items").fetchone()[0]
