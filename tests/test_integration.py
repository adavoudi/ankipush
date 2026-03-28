import os
import pytest
from ankipush import sync_deck
from ankipush.runner import build_image

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1",
    reason="Set RUN_INTEGRATION=1 to run integration tests",
)

EMAIL = "testuser"
PASSWORD = "testpass"
# With host networking the container reaches the host sync server via 172.17.0.1
SYNC_ENDPOINT = "http://172.17.0.1:8080/"


@pytest.fixture(scope="session", autouse=True)
def docker_image():
    print("\n[integration] Building ankipush Docker image...", flush=True)
    build_image()
    print("[integration] Image build complete.", flush=True)


@pytest.fixture(autouse=True)
def set_sync_endpoint(monkeypatch):
    monkeypatch.setenv("ANKI_SYNC_ENDPOINT", SYNC_ENDPOINT)


def _run(apkg_path, tmp_path, email=EMAIL, password=PASSWORD):
    print(f"\n[integration] Running sync_deck for {email} with {os.path.basename(apkg_path)}...", flush=True)
    sync_deck(email, password, apkg_path, data_dir=str(tmp_path))


def test_full_flow_succeeds(sync_server, tmp_path, shared_datadir):
    _run(str(shared_datadir / "deck.apkg"), tmp_path)


def test_invalid_credentials_raises(sync_server, tmp_path, shared_datadir):
    with pytest.raises(RuntimeError, match="exited with code 1"):
        _run(str(shared_datadir / "deck.apkg"), tmp_path, password="wrongpass")


def test_missing_apkg_raises(sync_server, tmp_path):
    with pytest.raises((FileNotFoundError, RuntimeError)):
        _run("/nonexistent/deck.apkg", tmp_path)


def test_second_run_merges(sync_server, tmp_path, shared_datadir):
    """Run twice — second run must not wipe data from the first."""
    _run(str(shared_datadir / "deck.apkg"), tmp_path)
    _run(str(shared_datadir / "deck.apkg"), tmp_path)
