"""Shared setup: every test runs against a throw-away database and Home Assistant's demo devices, never the real ones."""
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="fh-test-")
os.environ["FAMILYHUB_DB"] = os.path.join(_TMP, "test.db")
os.environ["HA_DEMO"] = "1"
for k in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "FAMILYHUB_PIN", "FAMILYHUB_LOCK_READS", "HA_URL", "HA_TOKEN"):
    os.environ.pop(k, None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
