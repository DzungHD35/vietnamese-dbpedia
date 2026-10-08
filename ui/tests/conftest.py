"""Fixture dùng chung: một TestClient cho cả phiên test (graph nạp đúng một lần)."""

import time

import pytest
from fastapi.testclient import TestClient

from ui.api.app import create_app
from ui.api.state import kg

LOAD_TIMEOUT = 180  # giây


@pytest.fixture(scope="session")
def client():
    with TestClient(create_app()) as c:
        deadline = time.time() + LOAD_TIMEOUT
        while not kg.ready and kg.error is None and time.time() < deadline:
            time.sleep(0.5)
        assert kg.ready, kg.error or "Graph chưa nạp xong"
        yield c
