import os
import pytest
from ankipush import sync_deck
from ankipush.runner import build_image

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1",
    reason="Set RUN_INTEGRATION=1 to run integration tests",
)

EMAIL = os.environ.get("ANKI_EMAIL", "")
PASSWORD = os.environ.get("ANKI_PASS", "")
APKG_PATH = os.environ.get("ANKI_APKG_PATH", "")


@pytest.fixture(scope="session", autouse=True)
def docker_image():
    build_image()


def test_full_flow_succeeds(tmp_path):
    sync_deck(EMAIL, PASSWORD, APKG_PATH, data_dir=str(tmp_path))


def test_invalid_credentials_raises(tmp_path):
    with pytest.raises(RuntimeError, match="exited with code 1"):
        sync_deck("bad@bad.com", "wrongpass", APKG_PATH, data_dir=str(tmp_path))


def test_missing_apkg_raises(tmp_path):
    with pytest.raises((FileNotFoundError, RuntimeError)):
        sync_deck(EMAIL, PASSWORD, "/nonexistent/deck.apkg", data_dir=str(tmp_path))
