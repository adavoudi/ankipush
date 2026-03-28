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
SYNC_ENDPOINT = "http://localhost:8080/"


@pytest.fixture(scope="session", autouse=True)
def docker_image():
    build_image()


def _extra_env():
    return {"ANKI_SYNC_ENDPOINT": SYNC_ENDPOINT}


def _run(apkg_path, tmp_path, email=EMAIL, password=PASSWORD):
    # Pass sync endpoint override via a wrapper that sets env before calling runner
    import ankipush.runner as runner
    original = runner.run_for_user

    def patched(e, p, a, data_dir=None, image="ankipush:latest"):
        import os, docker, re, shutil
        safe_id = re.sub(r"[^a-zA-Z0-9]", "_", e)
        data_dir = data_dir or runner._DEFAULT_DATA_DIR
        user_data = os.path.join(data_dir, safe_id, "anki-data")
        user_export = os.path.join(data_dir, safe_id, "export")
        os.makedirs(user_data, exist_ok=True)
        os.makedirs(user_export, exist_ok=True)
        dest = os.path.join(user_export, os.path.basename(a))
        shutil.copy2(a, dest)
        client = docker.from_env()
        container = client.containers.run(
            image=image,
            name=f"ankipush_{safe_id}_test",
            environment={
                "ANKI_EMAIL": e,
                "ANKI_PASS": p,
                "ANKI_APKG_PATH": f"/export/{os.path.basename(a)}",
                "ANKI_SYNC_ENDPOINT": SYNC_ENDPOINT,
            },
            volumes={
                user_data: {"bind": "/data", "mode": "rw"},
                user_export: {"bind": "/export", "mode": "rw"},
            },
            network_mode="host",
            detach=True,
            remove=False,
        )
        try:
            for line in container.logs(stream=True):
                print(line.decode().strip(), flush=True)
            container.reload()
            exit_code = container.attrs["State"]["ExitCode"]
            if exit_code != 0:
                raise RuntimeError(f"ankipush container exited with code {exit_code}")
        finally:
            container.remove(force=True)

    runner.run_for_user = patched
    try:
        sync_deck(email, password, apkg_path, data_dir=str(tmp_path))
    finally:
        runner.run_for_user = original


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
