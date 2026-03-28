import os
import subprocess
import time
import urllib.request
from pathlib import Path
import pytest

COMPOSE_FILE = os.path.join(os.path.dirname(__file__), "syncserver", "docker-compose.yml")
SYNC_SERVER_URL = "http://localhost:8080/"


@pytest.fixture(scope="session")
def shared_datadir():
    return Path(__file__).parent / "data"


def _wait_for_server(timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(SYNC_SERVER_URL, timeout=2)
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError(f"Sync server did not become ready within {timeout}s")


@pytest.fixture(scope="session", autouse=False)
def sync_server():
    if os.environ.get("RUN_INTEGRATION") != "1":
        yield
        return
    subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "up", "-d"], check=True)
    try:
        _wait_for_server()
        yield
    finally:
        subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "down", "-v"], check=True)
