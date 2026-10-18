import json
import os
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from testcontainers.community.postgres import PostgresContainer

from app.adapters.base_adapter import PROCESSING_EXT, EO_EXT

PROJECT_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = PROJECT_DIR / "samples"

EXPECTED_SKY_SHIELD_ITEM = {
    "type": "Feature",
    "stac_version": "1.1.0",
    "stac_extensions": [EO_EXT, PROCESSING_EXT],
    "id": "SKY_SHIELD_20260824_091522_L1C_POL",
    "collection": "SKY_SHIELD",
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [[20.912, 52.185], [21.245, 52.185], [21.245, 52.398], [20.912, 52.398], [20.912, 52.185]]
        ],
    },
    "bbox": [20.912, 52.185, 21.245, 52.398],
    "properties": {
        "datetime": "2026-08-24T09:15:22.451000Z",
        "platform": "SKY_SHIELD_03",
        "eo:cloud_cover": 14.2,
        "processing:level": "L1C",
    },
    "assets": {
        band: {
            "href": f"https://data.skyisnolimit.com/store/2026/08/24/SKY_SHIELD_{file}.tif",
            "type": "image/tiff; application=geotiff",
            "roles": ["data"],
        }
        for band, file in [("red", "B04"), ("green", "B03"), ("blue", "B02"), ("nir", "B08")]
    },
    "links": [{"rel": "collection", "href": "../../SKY_SHIELD", "type": "application/json"}],
}

EXPECTED_SPACE_EYE_ITEM = {
    "type": "Feature",
    "stac_version": "1.1.0",
    "stac_extensions": [EO_EXT, PROCESSING_EXT],
    "id": "SE02_L2A_20260824T104500_N001",
    "collection": "SPACE_EYE",
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [21.0, 52.3502933],
                [21.0, 51.3632417],
                [22.5765187, 51.3526339],
                [22.6113778, 52.3393051],
                [21.0, 52.3502933],
            ]
        ],
    },
    "bbox": [21.0, 51.3526339, 22.6113778, 52.3502933],
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

_postgres = PostgresContainer("postgis/postgis:18-3.6", driver=None).with_kwargs(platform="linux/amd64")


def pytest_sessionstart(session):
    if "DATABASE_URL" in os.environ:
        return
    _postgres.start()
    os.environ["DATABASE_URL"] = _postgres.get_connection_url()
    command.upgrade(Config(str(PROJECT_DIR / "alembic.ini")), "head")


def pytest_sessionfinish(session, exitstatus):
    if _postgres.get_wrapped_container() is not None:
        _postgres.stop()


@pytest.fixture
def sky_payload() -> bytes:
    return (SAMPLES_DIR / "SkyIsNoLimit.json").read_bytes()


@pytest.fixture
def space_payload() -> bytes:
    return (SAMPLES_DIR / "SpaceIsNoLimit.xml").read_bytes()


def as_json(item_dict: dict) -> dict:
    return json.loads(json.dumps(item_dict))


def edit_json(payload: bytes, edit) -> bytes:
    document = json.loads(payload)
    edit(document)
    return json.dumps(document).encode()


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

    def edit(payload: bytes) -> bytes:
        assert old in payload, f"{old!r} not found in the sample"
        return payload.replace(old, new)

    return edit


def apply(payload: bytes, *edits) -> bytes:
    for edit in edits:
        payload = edit(payload)
    return payload
