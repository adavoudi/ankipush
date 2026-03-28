import os
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path
import pytest

COMPOSE_FILE = os.path.join(os.path.dirname(__file__), "syncserver", "docker-compose.yml")
SYNC_SERVER_URL = "http://localhost:8080/"


@pytest.fixture(scope="session")
def shared_datadir():
    return Path(__file__).parent / "data"


def _wait_for_server(timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(SYNC_SERVER_URL + "sync/hostKey", timeout=2)
        except urllib.error.HTTPError:
            return  # any HTTP response means server is up
        except Exception:
            print(".", end="", flush=True)
            time.sleep(1)
    raise RuntimeError(f"Sync server did not become ready within {timeout}s")


@pytest.fixture(scope="session", autouse=False)
def sync_server():
    if os.environ.get("RUN_INTEGRATION") != "1":
        yield
        return
    print("\n[integration] Building sync server image...", flush=True)
    subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "build"], check=True)
    print("[integration] Starting sync server...", flush=True)
    subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "up", "-d"], check=True)
    try:
        print("[integration] Waiting for sync server to be ready...", flush=True)
        _wait_for_server(timeout=30)
        print("\n[integration] Sync server is ready.", flush=True)
        yield
    finally:
        print("\n[integration] Tearing down sync server...", flush=True)
        subprocess.run(["docker", "compose", "-f", COMPOSE_FILE, "down", "-v"], check=True)
