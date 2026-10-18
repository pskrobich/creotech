from pathlib import Path

import pytest

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture
def sky_payload() -> bytes:
    return (SAMPLES_DIR / "SkyIsNoLimit.json").read_bytes()


@pytest.fixture
def space_payload() -> bytes:
    return (SAMPLES_DIR / "SpaceIsNoLimit.xml").read_bytes()
